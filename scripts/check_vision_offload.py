#!/usr/bin/env python3
"""Helper to monitor vision.frame.offload from Rider-Pi."""

import argparse
import base64
import json
import logging
import time

from dotenv import load_dotenv

from pc_client.config.settings import Settings

try:
    import zmq
except ImportError:  # pragma: no cover
    zmq = None  # type: ignore

logger = logging.getLogger(__name__)


def decode_frame(payload: dict) -> int:
    frame = payload.get("frame_jpeg") or payload.get("frame_data") or ""
    if isinstance(frame, bytes):
        return len(frame)
    if isinstance(frame, str):
        try:
            decoded = base64.b64decode(frame, validate=True)
            return len(decoded)
        except Exception:
            return len(frame)
    return 0


def main() -> None:
    if zmq is None:
        raise SystemExit("pyzmq is required (pip install pyzmq)")

    load_dotenv()
    settings = Settings()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=settings.rider_pi_host, help="Rider-Pi ZMQ host")
    parser.add_argument("--port", type=int, default=settings.zmq_pub_port, help="ZMQ PUB port")
    parser.add_argument("--topic", default="vision.frame.offload", help="Topic to subscribe")
    parser.add_argument("--count", type=int, default=0, help="Stop after consuming this many frames (0=infinite)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Receive timeout (seconds)")
    args = parser.parse_args()

    endpoint = f"tcp://{args.host}:{args.port}"
    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.connect(endpoint)
    sock.setsockopt_string(zmq.SUBSCRIBE, args.topic)
    sock.setsockopt(zmq.RCVTIMEO, int(args.timeout * 1000))

    logger.info("Listening on %s (%s)", endpoint, args.topic)
    seen = 0
    last_ts = None
    start = time.time()

    try:
        while True:
            try:
                topic_bytes, payload_blob = sock.recv_multipart()
            except zmq.error.Again:
                logger.warning("no frames received for %.1fs", args.timeout)
                continue
            seen += 1
            topic_str = topic_bytes.decode("utf-8", "ignore")
            try:
                payload = json.loads(payload_blob.decode("utf-8"))
            except json.JSONDecodeError as exc:
                logger.error("failed to parse payload: %s", exc)
                payload = {}
            ts = payload.get("ts")
            if ts:
                delta = (ts - last_ts) if last_ts else 0
                last_ts = ts
            else:
                delta = None
            size = decode_frame(payload)
            meta = payload.get("meta") or {}
            detections = payload.get("detections")
            extra = f"detections={len(detections)}" if isinstance(detections, list) else ""
            print(
                f"[{seen}] topic={topic_str} ts={ts} delta={delta} size={size} {extra} fps={payload.get('fps') or 'n/a'}"
            )
            if args.count and seen >= args.count:
                break
    finally:
        duration = time.time() - start
        logger.info("received %d frames in %.1fs", seen, duration)
        sock.close()
        ctx.term()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    main()
