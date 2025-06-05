import sys
import os
import mediapipe as mp
import cv2
import csv

# Usage: python extract_pose.py --input input.mp4 --output output.pose.csv

def extract_pose(input_path, output_csv):
    mp_pose = mp.solutions.pose
    cap = cv2.VideoCapture(input_path)
    with mp_pose.Pose(static_image_mode=False) as pose, open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        header = ['frame'] + [f'{name}_{i}' for name in ['x','y','z','v'] for i in range(33)]
        writer.writerow(header)
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            row = [frame_idx]
            if results.pose_landmarks:
                for lm in results.pose_landmarks.landmark:
                    row += [lm.x, lm.y, lm.z, lm.visibility]
            else:
                row += [0]*33*4
            writer.writerow(row)
            frame_idx += 1
    cap.release()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    extract_pose(args.input, args.output)
