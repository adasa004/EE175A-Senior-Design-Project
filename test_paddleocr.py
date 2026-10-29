"""Test local PaddleOCR without the dashboard. No images are saved or uploaded."""
import argparse
import sys
import traceback


def print_results(engine, frame):
    print('\nRunning local OCR...', flush=True)
    results = engine.predict(frame)
    count = 0
    for result in results:
        for text, score in zip(result.get('rec_texts', []), result.get('rec_scores', [])):
            count += 1
            print(f'  TEXT: {text!s}    SCORE: {float(score):.1%}', flush=True)
    if not count:
        print('No text detected. Try a close, sharply focused printed example with good lighting.', flush=True)
    print('Done. These are raw text readings, with no license-plate filter.\n', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', nargs='?', help='Optional local image filename')
    parser.add_argument('--camera', action='store_true', help='Capture from the laptop webcam')
    parser.add_argument('--camera-index', type=int, default=0, help='Webcam index; default 0')
    args = parser.parse_args()
    if bool(args.image) == args.camera:
        parser.error('Choose either a local image filename or --camera.')

    print('Loading PaddleOCR on CPU. First use may download model files. Please wait.', flush=True)
    import paddle
    import paddleocr
    from paddleocr import PaddleOCR
    print(f'Python: {sys.version.split()[0]} | PaddlePaddle: {paddle.__version__} | PaddleOCR: {paddleocr.__version__}', flush=True)
    engine = PaddleOCR(lang='en', ocr_version='PP-OCRv5', device='cpu',
                       use_doc_orientation_classify=False, use_doc_unwarping=False,
                       use_textline_orientation=False)
    print('Model loaded.', flush=True)
    if args.image:
        from PIL import Image
        import numpy as np
        with Image.open(args.image) as image:
            frame = np.asarray(image.convert('RGB'))[:, :, ::-1].copy()
        print_results(engine, frame)
        return

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError('Webcam mode needs OpenCV (cv2). You can still test with an image filename instead.') from exc
    print('Close the website camera and other camera apps before testing.', flush=True)
    print('Hold a printed test plate close to the webcam. No preview window is used.', flush=True)
    while True:
        command = input('Press Enter to capture and read, or type q then Enter to quit: ').strip().lower()
        if command == 'q':
            break
        capture = cv2.VideoCapture(args.camera_index)
        try:
            if not capture.isOpened():
                raise RuntimeError('Cannot open webcam. Close other camera apps or try --camera-index 1.')
            # Give autofocus/exposure a moment to settle before reading the last frame.
            import time
            deadline = time.monotonic() + 2
            frame = None
            while time.monotonic() < deadline:
                ok, current = capture.read()
                if ok:
                    frame = current
                else:
                    time.sleep(0.05)
            if frame is None:
                raise RuntimeError('Webcam opened but no picture was received.')
        finally:
            capture.release()
        print_results(engine, frame)


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nStopped.')
    except Exception:
        print('\nOCR TEST FAILED. Copy the error below for troubleshooting:', file=sys.stderr, flush=True)
        traceback.print_exc()
        sys.exit(1)
