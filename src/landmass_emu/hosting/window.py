"""Digita `exit` na janela de um servidor de partida (Windows).

O motor só grava o `LOG=` da partida ao sair pelo console; `terminate` derruba o processo com o
buffer ainda dentro dele. Medido em 13/10/2026: `exit` saiu com código 0 em 0,1 s e o arquivo
passou de 8749 para 11199 bytes. A janela é `LandMassUnrealWLog`, com o terminal
`LandMassUnrealWEditTerminal` como filho. Só as janelas do PID informado são tocadas: os servidores
do usuário na faixa 7800-7899 têm a mesma classe.
"""

import ctypes
import sys
from ctypes import wintypes

_WM_KEYDOWN = 0x0100
_WM_KEYUP = 0x0101
_WM_CHAR = 0x0102
_VK_RETURN = 0x0D
# lParam de tecla: contagem 1 e scan code do Enter (0x1C). A soltura põe os bits de transição.
_ENTER_DOWN = 0x001C0001
_ENTER_UP = 0xC01C0001
_TERMINAL = "EditTerminal"
_EXIT_LINE = "exit"


def send_exit(pid: int) -> bool:
    """Digita `exit` e Enter no terminal das janelas de `pid`. Falso se não achar o terminal."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, enum_proc, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    topos: list[int] = []

    def ao_topo(hwnd: int, _lp: int) -> bool:
        dono = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(dono))
        if dono.value == pid:
            topos.append(hwnd)
        return True

    filhas: list[int] = []

    def ao_filha(hwnd: int, _lp: int) -> bool:
        filhas.append(hwnd)
        return True

    user32.EnumWindows(enum_proc(ao_topo), 0)
    for topo in topos:
        user32.EnumChildWindows(topo, enum_proc(ao_filha), 0)
    terminal = None
    for filha in filhas:
        classe = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(filha, classe, 256)
        if _TERMINAL in classe.value:
            terminal = filha
            break
    if terminal is None:
        return False
    for ch in _EXIT_LINE:
        user32.PostMessageW(terminal, _WM_CHAR, ord(ch), 0)
    user32.PostMessageW(terminal, _WM_KEYDOWN, _VK_RETURN, _ENTER_DOWN)
    user32.PostMessageW(terminal, _WM_CHAR, _VK_RETURN, 0)
    user32.PostMessageW(terminal, _WM_KEYUP, _VK_RETURN, _ENTER_UP)
    return True
