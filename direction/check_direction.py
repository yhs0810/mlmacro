import ctypes

user32 = ctypes.windll.user32
VK_LEFT = 0x25
VK_RIGHT = 0x27

def is_left_pressed():
    """왼쪽 방향키가 눌려있는지 확인"""
    return user32.GetAsyncKeyState(VK_LEFT) & 0x8000 != 0

def is_right_pressed():
    """오른쪽 방향키가 눌려있는지 확인"""
    return user32.GetAsyncKeyState(VK_RIGHT) & 0x8000 != 0
