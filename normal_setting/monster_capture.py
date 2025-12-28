import dearpygui.dearpygui as dpg
import mss
import numpy as np
import cv2
import os
import glob
import tkinter as tk
from PIL import Image, ImageTk

class StaticAreaSelector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")
        
        # 화면 전체 캡처 (Freeze 효과)
        with mss.mss() as sct:
            monitor = sct.monitors[0] # 전체 화면
            sct_img = sct.grab(monitor)
            self.img_np = np.array(sct_img)
            self.img_rgb = cv2.cvtColor(self.img_np, cv2.COLOR_BGRA2RGB)
            self.pil_img = Image.fromarray(self.img_rgb)
            self.tk_img = ImageTk.PhotoImage(self.pil_img)
            
        self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.result = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=2)

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        left = min(self.start_x, end_x)
        top = min(self.start_y, end_y)
        width = abs(self.start_x - end_x)
        height = abs(self.start_y - end_y)
        
        if width > 5 and height > 5:
            # 전체 화면 기준 좌표
            self.result = {"top": int(top), "left": int(left), "width": int(width), "height": int(height)}
            # 선택된 영역 이미지 추출 (저장용)
            self.captured_image = self.img_np[top:top+height, left:left+width]
        
        self.root.destroy()

    def get_region_and_image(self):
        self.root.mainloop()
        return self.result, getattr(self, 'captured_image', None)

def capture_monster(sender, app_data, user_data):
    """몬스터 영역 캡처 및 저장 (화면 정지 후 선택)"""
    selector = StaticAreaSelector()
    region, img = selector.get_region_and_image()
    
    if region and img is not None:
        try:
            # 저장 경로 설정
            save_dir = "tools/monster"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            # 다음 파일 번호 찾기
            existing_files = glob.glob(os.path.join(save_dir, "monster*.png"))
            next_idx = 0
            if existing_files:
                indices = []
                for f in existing_files:
                    try:
                        base = os.path.basename(f)
                        idx = int(base.replace("monster", "").replace(".png", ""))
                        indices.append(idx)
                    except:
                        pass
                if indices:
                    next_idx = max(indices) + 1
            
            save_path = os.path.join(save_dir, f"monster{next_idx}.png")
            
            # 이미지 저장 (이미 캡처된 이미지 사용)
            cv2.imwrite(save_path, img)
            print(f"Monster saved to {save_path}")
            
            # 템플릿 리로드 (즉시 반영)
            try:
                from training_area.training_area import load_monster_templates
                load_monster_templates()
            except Exception as e:
                print(f"Reload monster templates error: {e}")
                
        except Exception as e:
            print(f"Monster capture error: {e}")

def reset_monster_capture(sender, app_data, user_data):
    """몬스터 캡처 이미지 전체 삭제 및 초기화"""
    try:
        save_dir = "tools/monster"
        if os.path.exists(save_dir):
            files = glob.glob(os.path.join(save_dir, "monster*.png"))
            for f in files:
                try:
                    os.remove(f)
                except:
                    pass
            print("All monster capture images deleted.")
            
        # 템플릿 리로드 (즉시 반영)
        try:
            from training_area.training_area import load_monster_templates
            load_monster_templates()
        except Exception as e:
            print(f"Reload monster templates error: {e}")
            
    except Exception as e:
        print(f"Reset monster capture error: {e}")

def render_monster_capture():
    """UI 렌더링"""
    dpg.add_button(label="몬스터캡처", callback=capture_monster, width=120, height=30)
    dpg.add_spacer(width=10)
    dpg.add_button(label="몬스터초기화", callback=reset_monster_capture, width=120, height=30)
