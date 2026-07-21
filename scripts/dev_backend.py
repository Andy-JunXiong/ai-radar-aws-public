import argparse
import os
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AI Radar backend for local development.")
    parser.add_argument("--machine", default="local")
    parser.add_argument("--data-mode", choices=("live", "local"), default="live")
    parser.add_argument("--aws-profile", default="your-readonly-profile")
    parser.add_argument("--use-default-aws-credentials", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    log_path = repo_root / "backend-dev-local.log"

    log_file = log_path.open("a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file

    os.environ["AI_RADAR_BACKEND_PRELOAD_CACHE"] = "0"
    os.environ["AI_RADAR_USE_LOCAL_OUTPUT"] = "1" if args.data_mode == "local" else "0"
    if args.data_mode == "live":
        if args.use_default_aws_credentials:
            os.environ.pop("AWS_PROFILE", None)
        else:
            os.environ["AWS_PROFILE"] = args.aws_profile.strip()
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ.pop("ELECTRON_RUN_AS_NODE", None)

    os.chdir(backend_dir)
    sys.path.insert(0, str(backend_dir))

    print("=" * 72, flush=True)
    print(f"Backend dev runner start: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"Machine: {args.machine}", flush=True)
    print(f"Data mode: {args.data_mode}", flush=True)
    print(f"AWS profile: {os.environ.get('AWS_PROFILE') or 'default credential chain'}", flush=True)
    print(f"Backend: http://{args.host}:{args.port}", flush=True)
    print(f"Backend dir: {backend_dir}", flush=True)
    print(f"Log: {log_path}", flush=True)

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
