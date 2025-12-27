import dearpygui.dearpygui as dpg
import mss
import numpy as np
import cv2
import tkinter as tk

# mss 인스턴스 생성
sct = mss.mss()
monitor = sct.monitors[1]  # 주 모니터

# 선택 영역 상태
selected_region = None  # {top, left, width, height}

# 텍스처 데이터 초기화 (200x120, RGBA)
texture_data = np.zeros((120, 200, 4), dtype=np.float32)

# 플레이어 템플릿 및 마스크 준비
player_template_path = "tools/player_img/y_p.png"
player_template_raw = cv2.imread(player_template_path, cv2.IMREAD_UNCHANGED)

player_template = None
player_mask = None

# 자동 학습 관련 변수
learned_template = None
learned_mask = None
best_learned_score = 0.0
learning_threshold = 0.95  # 이 이상의 정확도일 때 학습

# 현재 플레이어 위치 (캔버스 좌표)
current_player_pos = None

if player_template_raw is not None:
    if player_template_raw.shape[2] == 4:
        player_template = cv2.cvtColor(player_template_raw, cv2.COLOR_BGRA2BGR)
        player_mask = player_template_raw[:, :, 3]
    else:
        player_template = player_template_raw
        hsv = cv2.cvtColor(player_template, cv2.COLOR_BGR2HSV)
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([30, 255, 255])
        player_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
else:
    pass

class AreaSelector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-fullscreen', True)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")
        
        self.canvas = tk.Canvas(self.root, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)
        
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
            self.result = {"top": int(top), "left": int(left), "width": int(width), "height": int(height)}
        
        self.root.destroy()

    def get_region(self):
        self.root.mainloop()
        return self.result

def update_minimap():
    global texture_data, learned_template, learned_mask, best_learned_score, current_player_pos
    
    # 영역이 선택되지 않았으면 캡처하지 않음
    if selected_region is None:
        return
    
    capture_area = selected_region
    
    try:
        img_mss = sct.grab(capture_area)
        img_np = np.array(img_mss)
        
        img_umat = cv2.UMat(img_np)
        img_bgr = cv2.cvtColor(img_umat, cv2.COLOR_BGRA2BGR)
        img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        player_pos_on_canvas = None
        best_score = 0
        
        # 학습된 템플릿 우선 사용, 없으면 기본 템플릿 사용
        current_template = learned_template if learned_template is not None else player_template
        current_mask = learned_mask if learned_mask is not None else player_mask
        
        # 1. 템플릿 매칭
        if current_template is not None:
            template_umat = cv2.UMat(current_template)
            mask_umat = cv2.UMat(current_mask)
            
            res = cv2.matchTemplate(img_bgr, template_umat, cv2.TM_CCORR_NORMED, mask=mask_umat)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= 0.97:
                best_score = max_val
                h, w = current_template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                player_pos_on_canvas = [(center_x / capture_area["width"]) * 200, (center_y / capture_area["height"]) * 120]
                
                # 자동 학습: 정확도가 매우 높을 때 현재 이미지를 새 템플릿으로 저장
                if max_val >= learning_threshold and max_val > best_learned_score:
                    img_bgr_cpu = img_bgr.get()
                    x, y = max_loc
                    new_template = img_bgr_cpu[y:y+h, x:x+w]
                    if new_template.shape[0] == h and new_template.shape[1] == w:
                        learned_template = new_template.copy()
                        hsv_template = cv2.cvtColor(learned_template, cv2.COLOR_BGR2HSV)
                        lower_yellow = np.array([20, 100, 100])
                        upper_yellow = np.array([35, 255, 255])
                        learned_mask = cv2.inRange(hsv_template, lower_yellow, upper_yellow)
                        best_learned_score = max_val
        
        # 2. 컬러 기반 추적 (백업)
        if player_pos_on_canvas is None or best_score < 0.85:
            lower_yellow = np.array([20, 100, 100])
            upper_yellow = np.array([35, 255, 255])
            
            mask = cv2.inRange(img_hsv, lower_yellow, upper_yellow)
            mask = cv2.erode(mask, None, iterations=2)
            mask = cv2.dilate(mask, None, iterations=2)
            
            mask_cpu = mask.get()
            contours, _ = cv2.findContours(mask_cpu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                c = max(contours, key=cv2.contourArea)
                if cv2.contourArea(c) > 10:
                    M = cv2.moments(c)
                    if M["m00"] != 0:
                        center_x = int(M["m10"] / M["m00"])
                        center_y = int(M["m01"] / M["m00"])
                        player_pos_on_canvas = [(center_x / capture_area["width"]) * 200, (center_y / capture_area["height"]) * 120]
        
        # 배경 이미지 업데이트
        img_rgba = cv2.cvtColor(img_umat, cv2.COLOR_BGRA2RGBA)
        img_resized = cv2.resize(img_rgba, (200, 120))
        texture_data = img_resized.get().astype(np.float32) / 255.0
        
        if dpg.does_item_exist("minimap_texture"):
            dpg.set_value("minimap_texture", texture_data)
        
        if dpg.does_item_exist("minimap_drawlist"):
            dpg.delete_item("minimap_drawlist", children_only=True)
            dpg.draw_image("minimap_texture", [0, 0], [200, 120], parent="minimap_drawlist")
            # 초록색 점으로 표시 (반지름 3으로 약간 더 크게)
            if player_pos_on_canvas:
                dpg.draw_circle(player_pos_on_canvas, 3, color=[0, 255, 0, 255], fill=[0, 255, 0, 255], parent="minimap_drawlist")
        
        # 플레이어 위치 업데이트
        current_player_pos = player_pos_on_canvas
                
    except Exception as e:
        pass

def get_player_position():
    """현재 플레이어 위치 반환 (캔버스 좌표)"""
    return current_player_pos

def start_selection():
    global selected_region
    selector = AreaSelector()
    region = selector.get_region()
    if region:
        selected_region = region

def render_minimap_settings():
    if not dpg.does_item_exist("minimap_texture_registry"):
        with dpg.texture_registry(tag="minimap_texture_registry"):
            dpg.add_dynamic_texture(width=200, height=120, default_value=texture_data, tag="minimap_texture")

    dpg.add_button(label="미니맵 영역 지정", callback=start_selection)
    dpg.add_spacer(height=5)
    
    with dpg.child_window(width=202, height=122, border=True, no_scrollbar=True, no_scroll_with_mouse=True):
        dpg.add_drawlist(width=200, height=120, tag="minimap_drawlist")
