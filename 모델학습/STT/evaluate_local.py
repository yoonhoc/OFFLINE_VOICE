import whisper
import time
import torch
import jiwer
import re
import os
import json
import numpy as np
import pandas as pd
import librosa
import soundfile as sf

# 이 스크립트가 있는 디렉토리를 기준으로 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def clean_text(text):
    # AI Hub 이중 전사 처리: (발음)/(철자) 형태에서 (철자) 부분의 텍스트만 추출
    text = re.sub(r'\((.*?)\)/\((.*?)\)', r'\2', text)
    text = re.sub(r'[.,!?]', '', text)
    return text.strip()

def evaluate_local():
    print("="*50)
    print("🖥️  노트북 로컬 STT 벤치마크 프로그램")
    print("="*50)
    
    # ----------------------------------------------------
    # 사용할 모델 크기를 변경하며 테스트해 보세요!
    # (선택지: "base", "small", "medium", "large-v3")
    # ----------------------------------------------------
    # ✅ 로컬 챗봇 배포용 모델 (whisper-small, ~900MB)
    model_size = "small"
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n[{model_size}] 모델을 로딩합니다... (환경: {device})")
    print("첫 실행 시 모델 다운로드로 인해 시간이 걸릴 수 있습니다.")
    
    model = whisper.load_model(model_size).to(device)
    
    # 스크립트 위치 기준으로 samples 폴더 자동 탐색
    samples_dir = os.path.join(SCRIPT_DIR, "samples")
    if not os.path.exists(samples_dir):
        print(f"\n❌ 오류: 'samples' 폴더를 찾을 수 없습니다.")
        print(f"   탐색 경로: {samples_dir}")
        print("   ZIP 압축을 올바르게 풀었는지 확인하세요.")
        return

    wav_files = [f for f in os.listdir(samples_dir) if f.endswith('.wav')]
    total_samples = len(wav_files)
    print(f"\n총 {total_samples}개의 오디오 샘플을 평가합니다...")
    
    results = []
    start_time = time.time()
    
    for i, wav_file in enumerate(wav_files):
        basename = wav_file.replace('.wav', '')
        wav_path = os.path.join(samples_dir, wav_file)
        json_path = os.path.join(samples_dir, f"{basename}.json")
        
        # 정답 읽기
        with open(json_path, "r", encoding="utf-8") as f:
            label_data = json.load(f)
            true_text = label_data.get("Transcription", {}).get("LabelText", "")
            
        if not true_text:
            continue
            
        # 오디오 읽기 및 16kHz 변환 (만약 ffmpeg 에러가 나면 pydub 등으로 대체 가능하나 librosa로 해결)
        try:
            audio_array, sr = sf.read(wav_path)
            if sr != 16000:
                audio_array = librosa.resample(audio_array, orig_sr=sr, target_sr=16000)
            if len(audio_array.shape) > 1:
                audio_array = librosa.to_mono(audio_array.T)
            audio_array = audio_array.astype(np.float32)
        except Exception as e:
            print(f"오디오 파일 로드 에러 ({wav_file}): {e}")
            continue
            
        # 오디오 길이 계산 (RTF용)
        audio_duration_sec = len(audio_array) / 16000.0

        # 추론 및 지연 시간 측정
        infer_start = time.time()
        result = model.transcribe(audio_array, language="ko")
        infer_time = time.time() - infer_start
        pred_text = result["text"]
        
        # 지표 계산
        clean_true = clean_text(true_text)
        clean_pred = clean_text(pred_text)
        
        try:
            wer = jiwer.wer(clean_true, clean_pred)
            cer = jiwer.cer(clean_true, clean_pred)
        except ValueError:
            continue

        # RTF: 추론시간 / 오디오길이 (1.0 미만이면 실시간 처리 가능)
        rtf = infer_time / audio_duration_sec if audio_duration_sec > 0 else 0.0

        results.append({
            "id": basename,
            "true_text": clean_true,
            "pred_text": clean_pred,
            "wer": wer,
            "cer": cer,
            "latency_sec": infer_time,
            "audio_duration_sec": audio_duration_sec,
            "rtf": rtf
        })
        
        if (i+1) % 10 == 0 or (i+1) == total_samples:
            current_cer = np.mean([r['cer'] for r in results]) * 100
            print(f"[{i+1}/{total_samples}] 누적 CER: {current_cer:.1f}%")

    total_time = time.time() - start_time

    df = pd.DataFrame(results)
    avg_wer = df["wer"].mean()
    avg_cer = df["cer"].mean()
    avg_latency = df["latency_sec"].mean()
    avg_rtf = df["rtf"].mean()

    print("\n" + "="*55)
    print(f"📊 whisper-{model_size} 로컬 벤치마크 결과")
    print("="*55)
    print(f"  평균 문자 오류율 (CER):          {avg_cer*100:.2f}%")
    print(f"  평균 단어 오류율 (WER):          {avg_wer*100:.2f}%")
    print(f"  문장당 평균 추론 시간 (Latency): {avg_latency:.3f}초")
    print(f"  평균 RTF (실시간비율):           {avg_rtf:.3f}  (< 1.0 이면 실시간 처리 가능)")
    print(f"  총 평가 샘플 수:                 {len(df)}개")
    print(f"  총 소요 시간:                    {total_time:.1f}초")
    print("="*55)

    csv_name = os.path.join(SCRIPT_DIR, f"local_results_{model_size}.csv")
    df.to_csv(csv_name, index=False, encoding="utf-8-sig")
    print(f"\n💾 상세 결과 저장 완료: {csv_name}")

if __name__ == "__main__":
    evaluate_local()
