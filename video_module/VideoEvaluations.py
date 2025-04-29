import cv2
import numpy as np
import tempfile
import os
import mediapipe as mp
from deepface import DeepFace
import json
import math
import librosa
from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score
from LLM_Module.newtranscriber import VideoTranscriber
import moviepy.editor as mpedit
import speech_recognition as sr
import whisper
import time


class VideoAnalyzer:
    def __init__(self, video_file, speedup_factor=10):
        print("[INIT] Initializing VideoAnalyzer...")
        self.video_file = video_file
        self.speedup_factor = speedup_factor

        self.whisper_model = whisper.load_model("tiny")

        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(static_image_mode=False)

        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1)

        
        self.smile_count = 0
        self.previous_smile = False
        self.cooldown_frames = 10
        self.current_cooldown = 0
        self.positive_expression_count=0

    

    def analyze_frame(self, frame):
        # print("[ANALYZE] Analyzing frame using MediaPipe...")
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if not results.pose_landmarks:
            print("[WARN] No pose detected.")
            return {"posture": 0, "Eye Contact": 0, "keypoints": None}

        landmarks = results.pose_landmarks.landmark

        # Convert normalized coordinates to pixel values
        frame_height, frame_width = frame.shape[:2]
        keypoints = [(int(lm.x * frame_width), int(lm.y * frame_height), lm.visibility) for lm in landmarks]

        result = {
            "posture": self.calculate_posture_score(keypoints),
            "Eye Contact": self.calculate_eye_contact_score(keypoints),
            "keypoints": keypoints
        }
        print(f"[ANALYZE] Posture: {result['posture']}, Eye Contact: {result['Eye Contact']}")
        return result
    

    def calculate_gesture_energy(self, frames):
        """
        Calculate hand gesture energy level from raw video frames using MediaPipe Pose.
        """
        mp_pose = mp.solutions.pose
        pose = mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5, model_complexity=1)

        left_wrist_positions = []
        right_wrist_positions = []
        left_elbow_positions = []
        right_elbow_positions = []
        left_shoulder_positions = []
        right_shoulder_positions = []

        for frame in frames:
            if frame is None:
                left_wrist_positions.append(None)
                right_wrist_positions.append(None)
                left_elbow_positions.append(None)
                right_elbow_positions.append(None)
                left_shoulder_positions.append(None)
                right_shoulder_positions.append(None)
                continue

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                # For wrist positions
                left_wrist = landmarks[15]
                right_wrist = landmarks[16]
                
                # Use wrist if visible, else use elbow or shoulder positions
                if left_wrist.visibility >= 0.5:
                    left_wrist_positions.append((left_wrist.x, left_wrist.y))
                    left_elbow_positions.append(None)
                    left_shoulder_positions.append(None)
                else:
                    left_wrist_positions.append(None)
                    if landmarks[13].visibility >= 0.5:  # Left elbow
                        left_elbow_positions.append((landmarks[13].x, landmarks[13].y))
                        left_shoulder_positions.append(None)
                    else:
                        left_elbow_positions.append(None)
                        if landmarks[11].visibility >= 0.5:  # Left shoulder
                            left_shoulder_positions.append((landmarks[11].x, landmarks[11].y))
                        else:
                            left_shoulder_positions.append(None)
                
                if right_wrist.visibility >= 0.5:
                    right_wrist_positions.append((right_wrist.x, right_wrist.y))
                    right_elbow_positions.append(None)
                    right_shoulder_positions.append(None)
                else:
                    right_wrist_positions.append(None)
                    if landmarks[14].visibility >= 0.5:  # Right elbow
                        right_elbow_positions.append((landmarks[14].x, landmarks[14].y))
                        right_shoulder_positions.append(None)
                    else:
                        right_elbow_positions.append(None)
                        if landmarks[12].visibility >= 0.5:  # Right shoulder
                            right_shoulder_positions.append((landmarks[12].x, landmarks[12].y))
                        else:
                            right_shoulder_positions.append(None)
            else:
                left_wrist_positions.append(None)
                right_wrist_positions.append(None)
                left_elbow_positions.append(None)
                right_elbow_positions.append(None)
                left_shoulder_positions.append(None)
                right_shoulder_positions.append(None)

        pose.close()

        def compute_motion(positions):
            total_motion = 0
            motion_frames = 0
            for i in range(1, len(positions)):
                if positions[i] is not None and positions[i - 1] is not None:
                    dx = positions[i][0] - positions[i - 1][0]
                    dy = positions[i][1] - positions[i - 1][1]
                    dist = np.sqrt(dx ** 2 + dy ** 2)
                    if dist > 0.01:  # filter out jitter/noise
                        total_motion += dist
                        motion_frames += 1
            return total_motion, motion_frames

        # Combine wrist, elbow, and shoulder motion for left and right side
        left_motion, _ = compute_motion(left_wrist_positions + left_elbow_positions + left_shoulder_positions)
        right_motion, _ = compute_motion(right_wrist_positions + right_elbow_positions + right_shoulder_positions)

        total_motion = left_motion + right_motion

        if all(pos is None for pos in left_wrist_positions + right_wrist_positions + left_elbow_positions + right_elbow_positions + left_shoulder_positions + right_shoulder_positions):
            return "hands not detected"

        movement_level = total_motion / len(frames)

        # Classify gesture energy
        if movement_level > 0.04:
            return "very high"
        elif movement_level > 0.025:
            return "high"
        elif movement_level > 0.015:
            return "medium"
        elif movement_level > 0.005:
            return "low"
        elif movement_level > 0:
            return "very low"
        else:
            return "hands not detected"


    def calculate_posture_score(self, keypoints):
        try:
            # Get keypoints in pixel coordinates
            nose = keypoints[0]
            right_shoulder = keypoints[12]
            left_shoulder = keypoints[11]
            left_wrist = keypoints[15]
            right_wrist = keypoints[16]


            head_x, head_y = nose[:2]
            rs_x, rs_y = right_shoulder[:2]
            ls_x, ls_y = left_shoulder[:2]


            # Midpoint between shoulders
            shoulder_mid_x = (rs_x + ls_x) / 2
            shoulder_mid_y = (rs_y + ls_y) / 2

            # Shoulder width (in pixels)
            shoulder_width = np.linalg.norm([rs_x - ls_x, rs_y - ls_y])
            shoulder_width = max(shoulder_width, 1e-6)  # Prevent divide-by-zero

            # Offset of head from shoulder center (in pixels)
            head_offset = np.linalg.norm([head_x - shoulder_mid_x, head_y - shoulder_mid_y])
            alignment_penalty = head_offset / (shoulder_width * 0.6)  # 60% of shoulder width is "acceptable"
            alignment_penalty = min(alignment_penalty, 2)
            print(f"[DEBUG] Head offset: {head_offset:.2f} px, Alignment penalty: {alignment_penalty:.4f}")

            # Shoulder tilt (in degrees)
            dx = rs_x - ls_x
            dy = rs_y - ls_y
            shoulder_angle = np.degrees(np.arctan2(dy, dx))

            # Normalize angle to range -90° to +90°
            if shoulder_angle > 90:
                shoulder_angle -= 180
            elif shoulder_angle < -90:
                shoulder_angle += 180

            tilt_penalty = min(abs(shoulder_angle) / 40, 2)  # 20°+ tilt = full penalty
            print(f"[DEBUG] Shoulder angle: {shoulder_angle:.2f}°, Tilt penalty: {tilt_penalty:.4f}")

            # Final score
            total_penalty = alignment_penalty + tilt_penalty
            posture_score = max(0, 5 - total_penalty)
            print(f"[DEBUG] Posture score: {posture_score:.2f}")

            # ========== Hand detection ==========
            hands_detected = all([
                left_wrist[0] != 0 and left_wrist[1] != 0,
                right_wrist[0] != 0 and right_wrist[1] != 0
            ])

            if hands_detected:
                print("Hand gestures are detected.")
            else:
                print("Hand gestures are not detected.")

            return int(round(posture_score))

        except Exception as e:
            print(f"[ERROR] Posture calculation failed: {e}")
            return 0


    def calculate_eye_contact_score(self, keypoints):
        try:
            # Get eye and nose coordinates
            nose_x, nose_y = keypoints[0][:2]
            left_eye_x, left_eye_y = keypoints[2][:2]
            right_eye_x, right_eye_y = keypoints[5][:2]

            # Calculate horizontal (x) and vertical (y) differences
            left_diff_x = abs(left_eye_x - nose_x)
            right_diff_x = abs(right_eye_x - nose_x)
            left_diff_y = abs(left_eye_y - nose_y)
            right_diff_y = abs(right_eye_y - nose_y)

            # Calculate eye distance (horizontal distance between eyes)
            eye_dist = np.linalg.norm([right_eye_x - left_eye_x, right_eye_y - left_eye_y])

            # Prevent division by zero in case of zero eye distance
            if eye_dist == 0:
                print("[WARNING] Eye distance is zero, skipping score.")
                return 0

            # Horizontal and vertical 
            horizontal_diff = (left_diff_x + right_diff_x) / eye_dist
            vertical_diff = (left_diff_y + right_diff_y) / eye_dist

            # Penalty factors
            base_penalty = (horizontal_diff ** 2.0) * 1  # Horizontal misalignment penalty
            vertical_penalty = (vertical_diff ** 2.0) * 1 # Vertical misalignment penalty

            # Combine the penalties
            total_penalty = min(base_penalty + vertical_penalty, 5)

            # Final eye score
            score = max(5 - total_penalty, 0)

            print(f"[DEBUG] base penalty: {base_penalty:.4f},vertical_penalty: {vertical_penalty:.4f},total_penalty: {total_penalty:.4f} Eye contact score: {score:.2f}")
            return int(round(score))
        except Exception as e:
            print(f"[ERROR] Eye contact score calculation failed: {e}")
            return 0


    def detect_smiles(self, frame):
        current_smile = False

        # Convert frame to RGB (MediaPipe expects RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                landmarks = face_landmarks.landmark

                #key landmark indices around the mouth
                left_ids = [61, 146, 91]
                right_ids = [291, 375, 321]
                top_ids = [13, 0, 11]
                bottom_ids = [14, 17, 84]

                def average_point(indices):
                    xs = [landmarks[i].x for i in indices]
                    ys = [landmarks[i].y for i in indices]
                    return np.mean(xs), np.mean(ys)

                # Compute mouth geometry
                left_x, left_y = average_point(left_ids)
                right_x, right_y = average_point(right_ids)
                top_x, top_y = average_point(top_ids)
                bottom_x, bottom_y = average_point(bottom_ids)

                mouth_width = np.linalg.norm([left_x - right_x, left_y - right_y])
                mouth_height = np.linalg.norm([top_y - bottom_y, top_x - bottom_x])

                # Prevent division by zero
                if mouth_height < 1e-6:
                    continue

                # Compute smile ratio
                ratio = mouth_width / mouth_height

                # Smile-specific cue: corners of the mouth higher than the center
                # A smile usually lifts the corners while top lip center stays neutral
                corners_avg_y = (left_y + right_y) / 2
                is_smile_shape = corners_avg_y < bottom_y  # corners lifted relative to bottom lip


                if ratio > 2.2 and is_smile_shape:
                    current_smile = True
                    print(f"[MediaPipe] Smile detected based on mouth ratio {ratio}")
                    break
        else:
            print("[MediaPipe] No face landmarks found.")

        # Handle smile detection cooldown
        if current_smile and self.current_cooldown == 0:
            self.smile_count += 1
            self.current_cooldown = self.cooldown_frames

        if self.current_cooldown > 0:
            self.current_cooldown -= 1
        try:
            result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            
            # Check if a face was detected
            if result and isinstance(result, list) and result[0].get("region"):
                region = result[0]['region']
                if region['w'] > 0 and region['h'] > 0:
                    emotion = result[0]['dominant_emotion']
                    # print(f"[DeepFace] Detected emotion: {emotion}")
                    if emotion in ['happy', 'surprise']:
                        self.positive_expression_count += 1
                        print(f"[INFO] Positive expression count: {self.positive_expression_count}")
                else:
                    print("[DeepFace] No face detected.")
            else:
                print("[DeepFace] No valid result.")
        except Exception as e:
            print(f"[DeepFace] Emotion detection error: {e}")

        return self.smile_count, self.positive_expression_count
    
    def extract_audio_features(self, video_path, duration_limit=None):
        print(f"\n[AUDIO] Starting audio feature extraction...")
        
        # Extract audio
        clip = mpedit.VideoFileClip(video_path)
        if duration_limit:
            clip = clip.subclip(0, duration_limit)
        
        temp_audio_path = "temp_audio.wav"
        clip.audio.write_audiofile(temp_audio_path, fps=16000, verbose=False, logger=None)
        
        y, sr_ = librosa.load(temp_audio_path, sr=16000)
        print(f"[AUDIO] Loaded audio: {len(y)} samples at {sr_} Hz")

        # Volume (RMS)
        rms = np.sqrt(np.mean(y**2))
        print(f"[AUDIO] Volume (RMS): {rms:.4f}")

        # Pitch (smoothed)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr_)
        pitch_values = pitches[magnitudes > np.median(magnitudes)]
        pitch = np.mean(pitch_values) if len(pitch_values) > 0 else 0
        print(f"[AUDIO] Pitch: {pitch:.2f} Hz")

        # Use Whisper for fast offline transcription
        print(f"[AUDIO] Transcribing using Whisper base model...")
        model = whisper.load_model("base")
        result = self.whisper_model.transcribe(temp_audio_path, fp16=False)
        text = result["text"]
        word_count = len(text.split())
        duration = duration_limit if duration_limit else clip.duration
        wpm = (word_count / duration) * 60
        print(f"[AUDIO] Transcribed text: {text[:100]}... ({word_count} words, {wpm:.2f} WPM)")

        return {"volume": rms, "pitch": pitch, "wpm": wpm}
    
    def normalize(self, val, min_val, max_val):
        print(f"[NORMALIZE] Raw value: {val:.4f}, Range: ({min_val} to {max_val})")
        scaled = 5 * (val - min_val) / (max_val - min_val)
        clipped = max(0, min(5, scaled))
        print(f"[NORMALIZE] Scaled value: {scaled:.4f}, Clipped to: {clipped:.2f}")
        return clipped

    def analyze_video(self):
        print("[VIDEO] Analyzing video...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
            temp_video_file.write(self.video_file.read())
            temp_video_path = temp_video_file.name


        cap = cv2.VideoCapture(temp_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        results = []
        gesture_frames = []

        print(f"[VIDEO] FPS: {fps}, Total Frames: {total_frames}")

        for frame_idx in range(0, total_frames, self.speedup_factor):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                print(f"[VIDEO] End of video at frame {frame_idx}.")
                break

            smile_detected = self.detect_smiles(frame)
            gesture_frames.append(frame)

            if frame_idx % (int(fps * 2) * self.speedup_factor) == 0:
                result = self.analyze_frame(frame)
                results.append(result)

        cap.release()
        # os.remove(temp_video_path)

        gesture_energy = self.calculate_gesture_energy(gesture_frames)
        print(f"[GESTURE] Energy level: {gesture_energy}")

        avg_posture = sum([res["posture"] for res in results]) / len(results) if results else 0
        avg_eye = sum([res["Eye Contact"] for res in results]) / len(results) if results else 0
        print(f"smile count:{self.smile_count}")
        video_duration = total_frames / fps
        smile_rate = self.smile_count / (video_duration / 60)
        # smile_score = min(5, (smile_rate / 5) * 5)
        smile_score = min(5, int(round(math.log1p(smile_rate))))

        positive_expression_rate=self.positive_expression_count/ (video_duration / 60)
        positive_expression_score=min(5, int(round(math.log1p(positive_expression_rate))))
        print(positive_expression_score)

        audio_features = self.extract_audio_features(temp_video_path)

        # Split metrics
        # voice_start = audio_features if video_duration <= 15 else self.extract_audio_features(temp_video_path, duration_limit=15)
        voice_total = audio_features

        # # Score normalization
        # energy_start = (
        #     self.normalize(voice_start["volume"], 0.01, 0.1) +
        #     self.normalize(voice_start["pitch"], 80, 300) +
        #     self.normalize(voice_start["wpm"], 80, 180)
        # ) / 3

        energy_total = (
            self.normalize(voice_total["volume"], 0.01, 0.1) +
            self.normalize(voice_total["pitch"], 80, 300) +
            self.normalize(voice_total["wpm"], 80, 180)
        ) / 3

        
        # audio_wav_path = os.path.join("audio", "temp_audio.wav")
        # audio_json_path = os.path.join("audio", "temp_transcript.json")
        # os.makedirs("audio", exist_ok=True)

        # transcriber = VideoTranscriber(temp_video_path, audio_wav_path, audio_json_path)
        # audio_features = transcriber.get_audio_features()

        # energy_total = (
        #     audio_features["volume"] +
        #     audio_features["pitch"] +
        #     audio_features["wpm"]
        # ) / 3

        print(f"volume:{audio_features['volume']}, pitch:{audio_features['pitch']}, wpm:{audio_features['wpm']}, energy:{energy_total}")

        # energetic_start = int(round((avg_posture + avg_eye + smile_score + energy_start) / 4))
        overall_energy = int(round((avg_posture + avg_eye + positive_expression_score + smile_score + energy_total) / 5))

        print(f"[RESULTS] Posture: {avg_posture}, Eye Contact: {avg_eye}, smile score:{smile_score}, video_duration:{video_duration}, overallEnergy:{overall_energy}")
        os.remove(temp_video_path)

        return {
            "posture": int(avg_posture),
            "Eye Contact": int(avg_eye),
            "Smile Score": int(smile_score),
            "Energy levels through the presentation": int(overall_energy),
            "positive_expression_score":int(positive_expression_score),
            "gesture_energy": gesture_energy
        }