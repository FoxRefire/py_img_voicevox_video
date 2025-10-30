#!/usr/bin/env python3
import os
import sys
import json
import requests
import subprocess
from tqdm import tqdm
from pathlib import Path
import wave
import argparse

VOICEVOX_URL = "http://127.0.0.1:50021"

def synthesize_voice(text, out_path, speaker_id=1, speed=1.0):
    """VOICEVOX APIで音声合成"""
    try:
        query = requests.post(
            f"{VOICEVOX_URL}/audio_query",
            params={"text": text, "speaker": speaker_id}
        )
        query.raise_for_status()
        query_json = query.json()
        query_json["speedScale"] = speed  # 読み上げ速度

        synth = requests.post(
            f"{VOICEVOX_URL}/synthesis",
            params={"speaker": speaker_id},
            data=json.dumps(query_json)
        )
        synth.raise_for_status()

        with open(out_path, "wb") as f:
            f.write(synth.content)
    except Exception as e:
        print(f"❌ 音声生成失敗: {text[:30]}... -> {e}")
        return False
    return True

def read_lines_with_paragraphs(path: Path):
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    return blocks

def get_wav_duration(path: Path):
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / rate

def main():
    parser = argparse.ArgumentParser(description="画像とVOICEVOX音声から動画を作成")
    parser.add_argument("images", type=str, help="画像フォルダ")
    parser.add_argument("lines", type=str, help="テキストファイル")
    parser.add_argument("-s", "--speed", type=float, default=1.0, help="読み上げ速度 (default=1.0)")
    parser.add_argument("-sp", "--speaker", type=int, default=1, help="VOICEVOX Speaker ID (default=1)")
    parser.add_argument("-o", "--output", type=str, default="output.mp4", help="出力ファイル名 (default=output.mp4)")

    args = parser.parse_args()

    frames_dir = Path(args.images)
    lines_file = Path(args.lines)

    if not frames_dir.is_dir() or not lines_file.exists():
        print("❌ 画像フォルダまたはテキストファイルが存在しません。")
        sys.exit(1)

    image_exts = (".png", ".jpg", ".jpeg", ".bmp")
    frames = sorted([p for p in frames_dir.iterdir() if p.suffix.lower() in image_exts])
    if not frames:
        print("❌ 画像ファイルが見つかりません。")
        sys.exit(1)

    lines = read_lines_with_paragraphs(lines_file)
    n = min(len(frames), len(lines))
    if n < len(lines):
        print(f"⚠️ 画像が不足しています ({len(frames)}枚, {len(lines)}セリフ)")
    elif n < len(frames):
        print(f"⚠️ セリフが不足しています ({len(frames)}枚, {len(lines)}セリフ)")

    audio_dir = Path("audio")
    video_dir = Path("clips")
    audio_dir.mkdir(exist_ok=True)
    video_dir.mkdir(exist_ok=True)

    for i in tqdm(range(n), desc="音声生成＆動画作成"):
        frame = frames[i]
        text = lines[i]
        audio = audio_dir / f"line{i+1:03d}.wav"
        clip = video_dir / f"clip{i+1:03d}.mp4"

        if not audio.exists():
            synthesize_voice(text, audio, speaker_id=args.speaker, speed=args.speed)

        duration = get_wav_duration(audio)

        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(frame),
                "-i", str(audio),
                "-c:v", "libx264",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-t", str(duration),
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                str(clip)
            ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ 動画生成失敗: {clip} -> {e}")

    with open("filelist.txt", "w", encoding="utf-8") as f:
        for i in range(1, n + 1):
            clip = video_dir / f"clip{i:03d}.mp4"
            if clip.exists():
                f.write(f"file '{clip}'\n")

    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", "filelist.txt", "-c", "copy", args.output
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 動画結合失敗 -> {e}")

    print(f"\n✅ 完成しました！ 出力ファイル: {args.output}")

if __name__ == "__main__":
    main()
