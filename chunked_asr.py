#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chunked_asr.py —— 用 sherpa-onnx Paraformer 把「分片 WAV」转成一份文本

场景
----
长音频（讲座、播客、口播视频）先切成小片，再逐片识别、最后合并成一份 transcript。
本脚本**只做识别这一步**，切片交给 ffmpeg —— 保持零业务耦合，也不联网。

用法
----
    # 1) 先切片：16kHz / 单声道 / 60 秒一片（Paraformer 要求 16k 单声道）
    ffmpeg -i input.mp3 -ar 16000 -ac 1 -vn -f segment -segment_time 60 chunks/chunk_%03d.wav

    # 2) 再识别
    python chunked_asr.py --chunks ./chunks \
        --model-dir ./sherpa-onnx-paraformer-zh-small \
        --out transcript.txt

依赖
----
    pip install sherpa-onnx numpy
    模型：任意 sherpa-onnx 兼容的 Paraformer 模型目录（需含 model.int8.onnx 与 tokens.txt）

设计要点
--------
- **静音守卫**：逐片先看峰值振幅，低于阈值的片直接跳过。
  实测价值有二：① 省算力；② 避免全静音片段送进 Paraformer 触发
  Conv/Reshape 形状异常导致进程崩溃（该现象在整段静音的片上稳定复现）。
- 逐片打印进度（片名 → 前 60 字），长任务可随时观察进展。
- 合并结果按片序以换行连接，不做去重与改写——保证「转写文本 = 模型原话」。
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import wave

import numpy as np
import sherpa_onnx


def read_wav(path: str) -> np.ndarray:
    """读取 16kHz 单声道 WAV，返回 [-1, 1] 的 float32 样本。"""
    with wave.open(path, "rb") as w:
        if w.getframerate() != 16000 or w.getnchannels() != 1:
            raise ValueError(
                "%s 不是 16kHz 单声道 WAV（当前 %dHz / %d 声道）；"
                "请按文件头的 ffmpeg 命令重新切片" % (path, w.getframerate(), w.getnchannels())
            )
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def main() -> int:
    ap = argparse.ArgumentParser(description="分片 WAV → 文本（sherpa-onnx Paraformer）")
    ap.add_argument("--chunks", required=True, help="分片目录（含 chunk_*.wav）")
    ap.add_argument("--model-dir", required=True,
                    help="Paraformer 模型目录（含 model.int8.onnx 与 tokens.txt）")
    ap.add_argument("--out", default="transcript.txt", help="输出文本路径（默认 transcript.txt）")
    ap.add_argument("--threshold", type=float, default=0.004,
                    help="静音阈值：峰值低于此值的分片跳过（默认 0.004）")
    ap.add_argument("--threads", type=int, default=8, help="推理线程数（默认 8）")
    ap.add_argument("--quiet", action="store_true", help="只输出最终结果行")
    a = ap.parse_args()

    model = os.path.join(a.model_dir, "model.int8.onnx")
    tokens = os.path.join(a.model_dir, "tokens.txt")
    for p in (model, tokens):
        if not os.path.exists(p):
            print("缺少模型文件: %s" % p, file=sys.stderr)
            return 2

    wavs = sorted(glob.glob(os.path.join(a.chunks, "chunk_*.wav")))
    if not wavs:
        print("在 %s 下没找到 chunk_*.wav" % a.chunks, file=sys.stderr)
        return 2
    if not a.quiet:
        print("分片数: %d" % len(wavs))

    rec = sherpa_onnx.OfflineRecognizer.from_paraformer(
        paraformer=model,
        tokens=tokens,
        num_threads=a.threads,
        sample_rate=16000,
        feature_dim=80,
    )

    parts, skipped = [], 0
    for wav in wavs:
        samples = read_wav(wav)
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        if peak < a.threshold:                       # 静音守卫（见文件头「设计要点」）
            skipped += 1
            if not a.quiet:
                print("%s -> (静音，跳过)" % os.path.basename(wav))
            continue
        stream = rec.create_stream()
        stream.accept_waveform(16000, samples)
        rec.decode_stream(stream)
        text = stream.result.text.strip()
        if not a.quiet:
            print("%s -> %s" % (os.path.basename(wav), text[:60] if text else "(空)"))
        if text:
            parts.append(text)

    merged = "\n".join(parts)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(merged)

    print("已写入 %s（%d 字符；%d 片有效，跳过静音 %d 片）"
          % (a.out, len(merged), len(parts), skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
