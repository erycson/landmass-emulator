"""Compila o pacote UnrealScript LMEmu e instala o LMEmu.u no servidor de partida.

Uso: uv run python unreal/build_lmemu.py [--landmass D:/landmass]

Ambiente em <landmass>/build:
- System/: cópia do system do servidor e o UCC.exe do patch 3369, corrigido por patch_ucc.py.
- Etc, Static, Unit e Map: junctions para o servidor, porque o LandMass.ini usa caminhos ../.
- LMEmu/Classes: fontes copiadas de unreal/LMEmu.

O make do UCC só compila pacote sem .u, então o LMEmu.u antigo é apagado antes.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = "LMEmu"
ASSET_DIRS = ("Etc", "Static", "Unit", "Map")
UCC_PATCH = Path("tools/UT2004-3369/UT2004-Patch/System/UCC.exe")


class LMEmuBuilder:
    def __init__(self, landmass: Path) -> None:
        self.server = landmass / "servidor-partida"
        self.build = landmass / "build"
        self.system = self.build / "System"
        self.ucc_source = landmass / UCC_PATCH

    def run(self) -> Path:
        self._prepare_system()
        self._link_assets()
        self._copy_sources()
        self._make()
        return self._install()

    def _prepare_system(self) -> None:
        shutil.copytree(self.server / "system", self.system, dirs_exist_ok=True)
        ucc = self.system / "ucc.exe"
        shutil.copy2(self.ucc_source, ucc)
        subprocess.run([sys.executable, str(HERE / "patch_ucc.py"), str(ucc)], check=True)
        ini = self.system / "LandMass.ini"
        lines = ini.read_text(encoding="ascii").splitlines()
        # UnrealEd.u não vem com o jogo, e o make para no primeiro pacote sem fonte nem .u.
        lines = [x for x in lines if x not in ("EditPackages=UnrealEd", f"EditPackages={PACKAGE}")]
        lines.insert(lines.index("EditPackages=UTV2004") + 1, f"EditPackages={PACKAGE}")
        ini.write_text("\n".join(lines) + "\n", encoding="ascii")

    def _link_assets(self) -> None:
        for name in ASSET_DIRS:
            link = self.build / name
            if not link.exists():
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(self.server / name)],
                    check=True,
                    capture_output=True,
                )

    def _copy_sources(self) -> None:
        target = self.build / PACKAGE
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(HERE / PACKAGE, target)

    def _make(self) -> None:
        (self.system / f"{PACKAGE}.u").unlink(missing_ok=True)
        result = subprocess.run(
            [
                str(self.system / "ucc.exe"),
                "Editor.MakeCommandlet",
                "-ini=LandMass.ini",
                "-userini=User.ini",
            ],
            cwd=self.system,
            capture_output=True,
            text=True,
            errors="replace",
        )
        print(result.stdout)
        if result.returncode != 0 or "Success - 0 error(s)" not in result.stdout:
            raise SystemExit(f"make falhou (código {result.returncode}); ver {self.system}/ucc.log")

    def _install(self) -> Path:
        built = self.system / f"{PACKAGE}.u"
        target = self.server / "system" / built.name
        shutil.copy2(built, target)
        return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--landmass", type=Path, default=Path("D:/landmass"))
    args = parser.parse_args()
    print("instalado:", LMEmuBuilder(args.landmass).run())


if __name__ == "__main__":
    main()
