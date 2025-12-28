import dearpygui.dearpygui as dpg
import mss
import numpy as np
import cv2
import threading
import os
import time
import ctypes
import glob
from normal_setting.minimap import AreaSelector

# mss 인스턴스 (메인 스레드에서 공유하거나 별도 생성)
sct = mss.mss()
monitor = sct.monitors[1]

# 몹 감지 구역 상태
mob_selected_region = None  # {top, left, width, height}
is_mob_window_open = True
current_mob_texture_tag = "mob_texture" # 현재 사용 중인 텍스처 태그

# 텍스처 데이터 초기화 (고정 크기 200x120)
mob_texture_width = 200
mob_texture_height = 120
mob_texture_data = np.zeros((mob_texture_height, mob_texture_width, 4), dtype=np.float32)

# 스레드 제어 변수
capture_thread = None
capture_running = False
latest_frame = None
frame_lock = threading.Lock()

# IGN 템플릿
ign_template = None
ign_template_path = "tools/ign/ign.png"

# 몬스터 템플릿 목록
monster_templates = []
monster_template_dir = "tools/monster"

def load_ign_template():
    """IGN 템플릿 로드"""
    global ign_template
    if os.path.exists(ign_template_path):
        try:
            # 한글 경로 지원을 위해 numpy로 읽기
            img_array = np.fromfile(ign_template_path, np.uint8)
            ign_template = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            print("IGN template loaded.")
        except Exception as e:
            print(f"Failed to load IGN template: {e}")
            ign_template = None
    else:
        ign_template = None

def load_monster_templates():
    """몬스터 템플릿 로드"""
    global monster_templates
    monster_templates = []
    
    if not os.path.exists(monster_template_dir):
        return
        
    files = glob.glob(os.path.join(monster_template_dir, "monster*.png"))
    for f in files:
        try:
            img_array = np.fromfile(f, np.uint8)
            tmpl = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if tmpl is not None:
                monster_templates.append(tmpl)
        except Exception as e:
            print(f"Failed to load monster template {f}: {e}")
    print(f"Loaded {len(monster_templates)} monster templates.")

# 초기 로드 시도
load_ign_template()
load_monster_templates()

import concurrent.futures

# OpenCL 사용 설정 (GPU 가속 시도)
try:
    cv2.ocl.setUseOpenCL(True)
except:
    pass

def process_template_batch(img_bgr, templates):
    """템플릿 배치를 처리하여 결과 좌표 반환 (별도 스레드에서 실행)"""
    results = []
    for tmpl in templates:
        try:
            # UMat을 사용하여 OpenCL(GPU) 가속 시도
            # img_umat = cv2.UMat(img_bgr)
            # tmpl_umat = cv2.UMat(tmpl)
            # res = cv2.matchTemplate(img_umat, tmpl_umat, cv2.TM_CCOEFF_NORMED)
            
            # 스레드 간 UMat 공유 문제 방지를 위해 일반 numpy 배열 사용 (안전성 우선)
            res = cv2.matchTemplate(img_bgr, tmpl, cv2.TM_CCOEFF_NORMED)
            
            threshold = 0.8
            loc = np.where(res >= threshold)
            h, w = tmpl.shape[:2]
            for pt in zip(*loc[::-1]):
                center_x = pt[0] + w // 2
                center_y = pt[1] + h // 2
                results.append((center_x, center_y))
        except:
            pass
    return results

def capture_loop():
    """고속 캡처 및 병렬 처리 루프 (별도 스레드)"""
    global latest_frame, capture_running, ign_template, monster_templates
    
    # 스레드 풀 생성 (최대 작업자 수 조절 가능)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    with mss.mss() as sct_thread:
        while capture_running:
            if mob_selected_region is None:
                time.sleep(0.1)
                continue
                
            try:
                # 1. 캡처
                raw = sct_thread.grab(mob_selected_region)
                img = np.array(raw)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # 2. 병렬 처리 (몬스터 추적)
                detected_points = []
                futures = []
                
                # 몬스터 템플릿을 3개씩 묶어서 처리
                batch_size = 3
                if monster_templates:
                    for i in range(0, len(monster_templates), batch_size):
                        batch = monster_templates[i:i + batch_size]
                        futures.append(executor.submit(process_template_batch, img_bgr, batch))
                
                # IGN 추적 (단일 템플릿이라 그냥 처리)
                if ign_template is not None:
                    try:
                        res = cv2.matchTemplate(img_bgr, ign_template, cv2.TM_CCOEFF_NORMED)
                        threshold = 0.8
                        loc = np.where(res >= threshold)
                        h, w = ign_template.shape[:2]
                        for pt in zip(*loc[::-1]):
                            # IGN 박스 (파란색 채움)
                            cv2.rectangle(img, pt, (pt[0] + w, pt[1] + h), (255, 0, 0, 255), -1)
                            
                            # 공격 범위 박스 (노란색 테두리)
                            try:
                                from attack_setting.attack_range import attack_range_x, attack_range_y
                                center_x = pt[0] + w // 2
                                center_y = pt[1] + h // 2
                                
                                x1 = center_x - attack_range_x
                                y1 = center_y - attack_range_y
                                x2 = center_x + attack_range_x
                                y2 = center_y + attack_range_y
                                
                                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0, 255), 5)
                            except:
                                pass
                    except: pass
                
                # 병렬 처리 결과 수집
                for future in concurrent.futures.as_completed(futures):
                    try:
                        points = future.result()
                        detected_points.extend(points)
                    except: pass
                
                # 결과 그리기 (메인 이미지에 통합)
                for pt in detected_points:
                    cv2.circle(img, pt, 7, (0, 255, 0, 255), -1)
                
                # 3. 결과 저장
                with frame_lock:
                    latest_frame = img
                
            except Exception as e:
                print(f"Capture thread error: {e}")
                time.sleep(1)

def start_capture_thread():
    """캡처 스레드 시작"""
    global capture_thread, capture_running
    if capture_thread is None or not capture_thread.is_alive():
        print("Starting capture thread...")
        capture_running = True
        capture_thread = threading.Thread(target=capture_loop, daemon=True)
        capture_thread.start()
    else:
        print("Capture thread already running.")

def select_mob_area(sender, app_data, user_data):
    """몹 감지 구역 선택"""
    global mob_selected_region
    
    selector = AreaSelector()
    region = selector.get_region()
    
    if region:
        print(f"Mob area selected: {region}")
        mob_selected_region = region
        # 캡처 스레드 시작 (이미 돌고 있으면 무시됨)
        start_capture_thread()

def create_mob_window():
    """몹 감지 확인용 윈도우 생성"""
    global current_mob_texture_tag
    
    if not dpg.does_item_exist("mob_texture_registry"):
        with dpg.texture_registry(tag="mob_texture_registry"):
            dpg.add_dynamic_texture(width=mob_texture_width, height=mob_texture_height, default_value=mob_texture_data, tag=current_mob_texture_tag)
            
    # 위치: 미니맵(510, 10, h=200) 아래 -> [510, 220]
    # 윈도우 크기 고정 (200x120 이미지 + 여백)
    with dpg.window(label="몹 감지 구역", tag="mob_window", width=220, height=160, 
                    no_scrollbar=True, show=True, pos=[510, 220]):
        with dpg.drawlist(width=mob_texture_width, height=mob_texture_height, tag="mob_drawlist"):
            dpg.draw_image(current_mob_texture_tag, [0, 0], [mob_texture_width, mob_texture_height], tag="mob_image")
        
        # 좌표 텍스트 추가
        with dpg.group(horizontal=True):
            dpg.add_text("X: - | Y: -", tag="mob_xy_text")
            dpg.add_spacer(width=20)
            dpg.add_text("FPS: 0", tag="mob_fps_text", color=[0, 255, 0])

# FPS 계산 변수
last_time = time.time()
frame_count = 0
current_fps = 0

def update_mob_area():
    """몹 감지 구역 실시간 업데이트 (메인 스레드 - 렌더링만 담당)"""
    global mob_texture_data, current_mob_texture_tag, latest_frame
    global last_time, frame_count, current_fps
    
    # FPS 계산
    current_time = time.time()
    frame_count += 1
    if current_time - last_time >= 1.0:
        current_fps = frame_count
        frame_count = 0
        last_time = current_time
        if dpg.does_item_exist("mob_fps_text"):
            dpg.set_value("mob_fps_text", f"FPS: {current_fps}")

    if not is_mob_window_open or mob_selected_region is None:
        return

    try:
        # 최신 프레임 가져오기 (이미 처리된 이미지)
        img = None
        with frame_lock:
            if latest_frame is not None:
                img = latest_frame.copy()
        
        if img is None:
            return

        # BGRA -> RGBA 변환 (표시용)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        
        # 크기 조정 (200x120) - cv2.INTER_NEAREST가 더 빠름
        img = cv2.resize(img, (mob_texture_width, mob_texture_height), interpolation=cv2.INTER_NEAREST)
        
        # float32로 변환 및 정규화
        data = img.astype(np.float32) / 255.0
        
        # 텍스처 업데이트
        if dpg.does_item_exist(current_mob_texture_tag):
            dpg.set_value(current_mob_texture_tag, data)
            
        # 좌표 업데이트
        from normal_setting import minimap
        pos = minimap.get_player_position()
        if pos and dpg.does_item_exist("mob_xy_text"):
             dpg.set_value("mob_xy_text", f"X: {pos[0]:.1f} | Y: {pos[1]:.1f}")
            
    except Exception as e:
        print(f"Mob area update error: {e}")

def toggle_mob_window():
    """T키로 윈도우 토글"""
    global is_mob_window_open
    is_mob_window_open = not is_mob_window_open
    if dpg.does_item_exist("mob_window"):
        if is_mob_window_open:
            dpg.show_item("mob_window")
        else:
            dpg.hide_item("mob_window")

def render_training_area():
    """UI 렌더링"""
    dpg.add_button(label="몹감지구역", callback=select_mob_area, width=120, height=30)
