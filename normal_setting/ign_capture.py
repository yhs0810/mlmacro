import dearpygui.dearpygui as dpg
import mss
import numpy as np
import cv2
import os
from normal_setting.minimap import AreaSelector

def capture_ign(sender, app_data, user_data):
    """닉네임 영역 캡처 및 저장"""
    selector = AreaSelector()
    region = selector.get_region()
    
    if region:
        try:
            with mss.mss() as sct:
                # 화면 캡처
                img = np.array(sct.grab(region))
                
                # BGRA -> BGR (OpenCV 저장용)
                # mss는 BGRA 반환, cv2.imwrite는 BGR 기대 (또는 BGRA도 가능하지만 투명도 필요없으면 BGR)
                # png 저장이므로 투명도 유지해도 됨. 그냥 저장.
                
                # 저장 경로 설정
                save_dir = "tools/ign"
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                    
                save_path = os.path.join(save_dir, "ign.png")
                
                # 이미지 저장 (덮어쓰기)
                cv2.imwrite(save_path, img)
                print(f"Nickname saved to {save_path}")
                
                # 템플릿 리로드 (즉시 반영)
                try:
                    from training_area.training_area import load_ign_template
                    load_ign_template()
                except Exception as e:
                    print(f"Reload template error: {e}")
                
        except Exception as e:
            print(f"IGN capture error: {e}")

def render_ign_capture():
    """UI 렌더링"""
    dpg.add_button(label="닉네임 캡쳐", callback=capture_ign, width=120, height=30)
