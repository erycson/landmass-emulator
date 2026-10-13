"""Controle do cliente LandMass para testes de aceite: screenshot interno (F11), cursor e clique.

O UE2 lê o mouse por deltas (DirectInput); SetCursorPos não move o cursor da GUI. O cursor não é
limitado às bordas, então posiciona em malha fechada: screenshot -> localiza a ponta -> delta.

Uso:
  uv run --no-project --with pillow python -I scripts/gui.py shot <saida.png> [--pid N]
  uv run --no-project --with pillow python -I scripts/gui.py click <x> <y> [--double] [--pid N]
  uv run --no-project --with pillow python -I scripts/gui.py type <texto> [--pid N]
  uv run --no-project --with pillow python -I scripts/gui.py key <vk> [--pid N]
"""

import argparse
import ctypes
import subprocess
import time
from pathlib import Path

from PIL import Image

user32 = ctypes.windll.user32
MICKEYS_PER_PX = 4.0  # medido com a sensibilidade padrão do User.ini
VK_F11 = 0x7A
SHOT_DIR_NAME = "ScreenShots"


def _proc(pid: int | None) -> tuple[int, Path]:
    flt = f"Id -eq {pid}" if pid else "ProcessName -eq 'LandMass'"
    out = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Get-Process | Where-Object {{ $_.{flt} }} | Select-Object -First 1 | "
            'ForEach-Object { "$($_.MainWindowHandle) $($_.Path)" }',
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    hwnd, path = out.split(" ", 1)
    return int(hwnd), Path(path)


def _focus(hwnd: int) -> None:
    # Windows só cede o foco a quem recebeu input por último; um ALT sintético libera o bloqueio.
    for _ in range(5):
        if user32.GetForegroundWindow() == hwnd:
            return
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    # Sem foco, mouse_event e keybd_event atingiriam outra janela do usuário.
    raise RuntimeError("o jogo não está em primeiro plano; abortado para não clicar fora dele")


def _key(vk: int) -> None:
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.08)
    user32.keybd_event(vk, 0, 2, 0)


def shot(out: Path, pid: int | None = None) -> Path:
    hwnd, exe = _proc(pid)
    shots = exe.parent.parent / SHOT_DIR_NAME
    before = set(shots.glob("*.bmp"))
    _focus(hwnd)
    _key(VK_F11)
    for _ in range(40):
        time.sleep(0.25)
        new = set(shots.glob("*.bmp")) - before
        if new:
            break
    else:
        raise TimeoutError("o jogo não gravou o screenshot")
    time.sleep(0.4)
    bmp = new.pop()
    Image.open(bmp).save(out)
    bmp.unlink()
    return out


def _is_cursor(r: int, g: int, b: int) -> bool:
    return b > 200 and r < 90 and 110 < g < 200


def find_cursor(png: Path) -> tuple[int, int] | None:
    im = Image.open(png).convert("RGB")
    px = im.load()
    w, h = im.size
    # O banner do topo também é azul; botões azuis (ex.: "Geral") são descartados pelo tamanho.
    blue = {(x, y) for y in range(95, h) for x in range(w) if _is_cursor(*px[x, y])}
    for comp in _components(blue):
        xs = [x for x, _ in comp]
        ys = [y for _, y in comp]
        if max(xs) - min(xs) <= CURSOR_MAX and max(ys) - min(ys) <= CURSOR_MAX and len(comp) >= 8:
            top = min(ys)
            return min(x for x, y in comp if y <= top + 1), top
    return None


CURSOR_MAX = 24  # o cursor tem ~14x20 px


def _components(pts: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    out, seen = [], set()
    for p in sorted(pts, key=lambda q: (q[1], q[0])):
        if p in seen:
            continue
        stack, comp = [p], []
        seen.add(p)
        while stack:
            x, y = stack.pop()
            comp.append((x, y))
            for q in ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                if q in pts and q not in seen:
                    seen.add(q)
                    stack.append(q)
        out.append(comp)
    return out


def _move(dx_px: float, dy_px: float) -> None:
    # Chamado só após _focus(); o jogo captura o mouse (CaptureMouse=True) enquanto tem foco.
    mx, my = round(dx_px * MICKEYS_PER_PX), round(dy_px * MICKEYS_PER_PX)
    steps = max(1, max(abs(mx), abs(my)) // 8)
    for i in range(steps):
        sx = mx * (i + 1) // steps - mx * i // steps
        sy = my * (i + 1) // steps - my * i // steps
        user32.mouse_event(0x01, sx, sy, 0, 0)
        time.sleep(0.01)


def goto(x: int, y: int, pid: int | None, tmp: Path) -> tuple[int, int]:
    hwnd, _ = _proc(pid)
    for _ in range(8):
        pos = find_cursor(shot(tmp, pid))
        if pos is None:  # cursor fora da área útil: traz para o centro
            _focus(hwnd)
            _move(400 - 20, 300 - 20)
            continue
        if abs(pos[0] - x) <= 2 and abs(pos[1] - y) <= 2:
            return pos
        _focus(hwnd)
        _move(x - pos[0], y - pos[1])
    raise RuntimeError(f"cursor não convergiu para ({x},{y}); último {pos}")


def click(x: int, y: int, double: bool, pid: int | None, tmp: Path) -> tuple[int, int]:
    pos = goto(x, y, pid, tmp)
    _focus(_proc(pid)[0])
    for _ in range(2 if double else 1):
        user32.mouse_event(0x02, 0, 0, 0, 0)
        time.sleep(0.06)
        user32.mouse_event(0x04, 0, 0, 0, 0)
        time.sleep(0.09)
    return pos


def type_text(text: str, pid: int | None) -> None:
    hwnd, _ = _proc(pid)
    _focus(hwnd)
    for ch in text:
        vk = user32.VkKeyScanW(ord(ch))
        shift = (vk >> 8) & 1
        if shift:
            user32.keybd_event(0x10, 0, 0, 0)
        _key(vk & 0xFF)
        if shift:
            user32.keybd_event(0x10, 0, 2, 0)
        time.sleep(0.03)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["shot", "click", "type", "key"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--double", action="store_true")
    ap.add_argument("--pid", type=int)
    ap.add_argument("--tmp", type=Path, default=Path("gui_tmp.png"))
    a = ap.parse_args()
    if a.cmd == "shot":
        print(shot(Path(a.args[0]), a.pid))
    elif a.cmd == "click":
        print("cursor", click(int(a.args[0]), int(a.args[1]), a.double, a.pid, a.tmp))
    elif a.cmd == "type":
        type_text(" ".join(a.args), a.pid)
    else:
        hwnd, _ = _proc(a.pid)
        _focus(hwnd)
        _key(int(a.args[0], 0))


if __name__ == "__main__":
    main()
