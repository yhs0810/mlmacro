import dearpygui.dearpygui as dpg
import mss
import numpy as np
import cv2
import tkinter as tk
import threading
import time

# mss 인스턴스 생성
sct = mss.mss()
monitor = sct.monitors[1]  # 주 모니터

# 선택 영역 상태
selected_region = None  # {top, left, width, height}

# 텍스처 데이터 초기화 (200x120, RGBA)
texture_data = np.zeros((120, 200, 4), dtype=np.float32)

# 스레드 제어 변수
capture_thread = None
capture_running = False
latest_frame = None
frame_lock = threading.Lock()

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

def capture_loop():
    """고속 캡처 루프 (별도 스레드)"""
    global latest_frame, capture_running, learned_template, learned_mask, best_learned_score, current_player_pos
    
    with mss.mss() as sct_thread:
        while capture_running:
            if selected_region is None:
                time.sleep(0.1)
                continue
                
            try:
                # 캡처 (가장 빠른 속도로)
                img_mss = sct_thread.grab(selected_region)
                img_np = np.array(img_mss)
                
                # 스레드 안전하게 저장
                with frame_lock:
                    latest_frame = img_np
                
                # CPU 점유율 조절
                # time.sleep(0.001)
                
            except Exception as e:
                time.sleep(1)

def start_capture_thread():
    """캡처 스레드 시작"""
    global capture_thread, capture_running
    if capture_thread is None or not capture_thread.is_alive():
        capture_running = True
        capture_thread = threading.Thread(target=capture_loop, daemon=True)
        capture_thread.start()

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

# FPS 계산 변수
last_time = time.time()
frame_count = 0
current_fps = 0

def update_minimap():
    global texture_data, learned_template, learned_mask, best_learned_score, current_player_pos, latest_frame
    global last_time, frame_count, current_fps
    
    # FPS 계산
    current_time = time.time()
    frame_count += 1
    if current_time - last_time >= 1.0:
        current_fps = frame_count
        frame_count = 0
        last_time = current_time
        if dpg.does_item_exist("minimap_fps_text"):
            dpg.set_value("minimap_fps_text", f"FPS: {current_fps}")

    # 영역이 선택되지 않았으면 캡처하지 않음
    if selected_region is None:
        return
    
    capture_area = selected_region
    
    try:
        # 최신 프레임 가져오기 (스레드에서 캡처한 것)
        img_np = None
        with frame_lock:
            if latest_frame is not None:
                img_np = latest_frame.copy()
        
        if img_np is None:
            return
        
        # CPU 연산 (UMat 사용 최소화, 스레드 분리 효과로 충분히 빠름)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        player_pos_on_canvas = None
        best_score = 0
        
        # 학습된 템플릿 우선 사용, 없으면 기본 템플릿 사용
        current_template = learned_template if learned_template is not None else player_template
        current_mask = learned_mask if learned_mask is not None else player_mask
        
        # 1. 템플릿 매칭
        if current_template is not None:
            res = cv2.matchTemplate(img_bgr, current_template, cv2.TM_CCORR_NORMED, mask=current_mask)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= 0.97:
                best_score = max_val
                h, w = current_template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                player_pos_on_canvas = [(center_x / capture_area["width"]) * 200, (center_y / capture_area["height"]) * 120]
                
                # 자동 학습: 정확도가 매우 높을 때 현재 이미지를 새 템플릿으로 저장
                if max_val >= learning_threshold and max_val > best_learned_score:
                    x, y = max_loc
                    new_template = img_bgr[y:y+h, x:x+w]
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
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                c = max(contours, key=cv2.contourArea)
                if cv2.contourArea(c) > 10:
                    M = cv2.moments(c)
                    if M["m00"] != 0:
                        center_x = int(M["m10"] / M["m00"])
                        center_y = int(M["m01"] / M["m00"])
                        player_pos_on_canvas = [(center_x / capture_area["width"]) * 200, (center_y / capture_area["height"]) * 120]
        
        # 배경 이미지 업데이트
        img_rgba = cv2.cvtColor(img_np, cv2.COLOR_BGRA2RGBA)
        img_resized = cv2.resize(img_rgba, (200, 120), interpolation=cv2.INTER_NEAREST)
        texture_data = img_resized.astype(np.float32) / 255.0
        
        if dpg.does_item_exist("minimap_texture"):
            dpg.set_value("minimap_texture", texture_data)
        
        if dpg.does_item_exist("minimap_drawlist"):
            dpg.delete_item("minimap_drawlist", children_only=True)
            dpg.draw_image("minimap_texture", [0, 0], [200, 120], parent="minimap_drawlist")
            
            # 층 구역 가로선 그리기 (파란색)
            try:
                from floor import f_setting
                # 모든 구역 순회하여 가로선 그리기
                for zone in f_setting.zone_data:
                    if zone['y'] is not None:
                        line_y = zone['y']
                        line_left_x = zone['left_x']
                        line_right_x = zone['right_x']
                        
                        # X값 정렬 (사용자가 반대로 입력했을 경우 대비)
                        actual_left = min(line_left_x, line_right_x)
                        actual_right = max(line_left_x, line_right_x)
                        
                        dpg.draw_line([actual_left, line_y], [actual_right, line_y], 
                                      color=[0, 100, 255, 255], thickness=2, parent="minimap_drawlist")
            except:
                pass

            # 사다리 좌표 표시 (초록색 점)
            try:
                from ladder.ladder import ladder_data
                for ladder in ladder_data:
                    if ladder['x'] is not None and ladder['y'] is not None:
                        dpg.draw_circle([ladder['x'], ladder['y']], 3, color=[0, 255, 0, 255], fill=[0, 255, 0, 255], parent="minimap_drawlist")
            except:
                pass
            
            # 점프다운 좌표 표시 (분홍색 점)
            try:
                from jump_down.j_d import jump_down_data
                for jd in jump_down_data:
                    if jd['x'] is not None and jd['y'] is not None:
                        dpg.draw_circle([jd['x'], jd['y']], 3, color=[255, 0, 255, 255], fill=[255, 0, 255, 255], parent="minimap_drawlist")
            except:
                pass
            
            # 초록색 점으로 플레이어 표시
            if player_pos_on_canvas:
                dpg.draw_circle(player_pos_on_canvas, 3, color=[0, 255, 0, 255], fill=[0, 255, 0, 255], parent="minimap_drawlist")
        
        # 플레이어 위치 업데이트
        current_player_pos = player_pos_on_canvas
        
        # 좌표 텍스트 업데이트
        if dpg.does_item_exist("minimap_xy_text"):
            if current_player_pos:
                dpg.set_value("minimap_xy_text", f"X: {current_player_pos[0]:.1f} | Y: {current_player_pos[1]:.1f}")
            else:
                dpg.set_value("minimap_xy_text", "X: - | Y: -")
                
    except Exception as e:
        pass

def get_player_position():
    """현재 플레이어 위치 반환 (캔버스 좌표)"""
    return current_player_pos

def start_selection(sender=None, app_data=None):
    global selected_region
    selector = AreaSelector()
    region = selector.get_region()
    if region:
        selected_region = region
        # 캡처 스레드 시작
        start_capture_thread()

# 미니맵 윈도우 표시 상태
minimap_window_visible = True

def toggle_minimap():
    """M키로 미니맵 윈도우 토글"""
    global minimap_window_visible
    if dpg.does_item_exist("minimap_window"):
        minimap_window_visible = not minimap_window_visible
        dpg.configure_item("minimap_window", show=minimap_window_visible)

def create_minimap_window():
    """별도의 미니맵 윈도우 생성"""
    if not dpg.does_item_exist("minimap_texture_registry"):
        with dpg.texture_registry(tag="minimap_texture_registry"):
            dpg.add_dynamic_texture(width=200, height=120, default_value=texture_data, tag="minimap_texture")
    
    with dpg.window(label="미니맵", tag="minimap_window", width=220, height=220, 
                    no_collapse=True, no_scrollbar=True, show=True, pos=[510, 10]):
        dpg.add_drawlist(width=200, height=120, tag="minimap_drawlist")
        with dpg.group(horizontal=True):
            dpg.add_text("X: - | Y: -", tag="minimap_xy_text")
            dpg.add_spacer(width=20)
            dpg.add_text("FPS: 0", tag="minimap_fps_text", color=[0, 255, 0])

def render_minimap_settings():
    """메인 GUI에 미니맵 설정 버튼만 표시"""
    dpg.add_button(label="미니맵 영역 지정", callback=start_selection, width=120, height=30)
    dpg.add_text("M키: 미니맵 창 열기/닫기", color=[150, 150, 150])
