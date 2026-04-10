#!/usr/bin/env python3
"""
Music Agent - wrapper around ACE-Step 1.5 for music generation.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add ace_step_1_5 to path
AGENT_DIR = Path(__file__).parent
ACE_STEP_DIR = AGENT_DIR / "ace_step_1_5"
sys.path.insert(0, str(ACE_STEP_DIR))


class MusicAgent:
    """
    Agent wrapper for ACE-Step 1.5 music generation.

    Two usage modes:
    1. API mode  - connects to a running ACE-Step API server (default)
    2. Direct mode - loads model in-process (heavy, requires GPU/VRAM)
    """

    def __init__(self, api_url: str = "http://localhost:7865", api_key: str | None = None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or os.getenv("ACESTEP_API_KEY")
        self._session = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        lyrics: str = "",
        duration: int = 60,
        bpm: int | None = None,
        key: str | None = None,
        output_path: str | Path = "output.mp3",
        audio_format: str = "mp3",
        inference_steps: int = 20,
        guidance_scale: float = 7.0,
        seed: int | None = None,
        thinking: bool = True,
    ) -> dict:
        """
        Generate music from a text prompt.

        Args:
            prompt: Natural language music description.
            lyrics: Optional song lyrics (50+ languages supported).
            duration: Length in seconds (10-600).
            bpm: Tempo hint (optional).
            key: Key hint e.g. "C major" (optional).
            output_path: Where to save the generated audio.
            audio_format: mp3 | flac | opus | aac | wav | wav32.
            inference_steps: Quality vs speed (1-20 turbo, 1-200 full).
            guidance_scale: Prompt adherence (default 7.0).
            seed: Reproducibility seed (optional).
            thinking: Use LLM planning step (default True).

        Returns:
            dict with keys: path, task_id, duration, metadata
        """
        import requests

        payload = {
            "prompt": prompt,
            "lyrics": lyrics,
            "audio_duration": duration,
            "audio_format": audio_format,
            "inference_steps": inference_steps,
            "guidance_scale": guidance_scale,
            "thinking": thinking,
        }
        if bpm:
            payload["bpm"] = bpm
        if key:
            payload["key"] = key
        if seed is not None:
            payload["seed"] = seed
        if self.api_key:
            payload["ai_token"] = self.api_key

        # Submit task
        resp = requests.post(f"{self.api_url}/release_task", json=payload, timeout=30)
        resp.raise_for_status()
        task_id = resp.json()["task_id"]

        # Poll until done
        audio_url = self._wait_for_result(task_id)

        # Download audio
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_resp = requests.get(audio_url, timeout=120)
        audio_resp.raise_for_status()
        output_path.write_bytes(audio_resp.content)

        return {
            "path": str(output_path),
            "task_id": task_id,
            "duration": duration,
            "audio_url": audio_url,
        }

    def analyze(self, audio_path: str | Path) -> dict:
        """
        Extract metadata from an existing audio file.

        Returns dict with: caption, bpm, key, language, timestamps
        """
        import requests

        with open(audio_path, "rb") as f:
            resp = requests.post(
                f"{self.api_url}/v1/understand",
                files={"audio": f},
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json()

    def health(self) -> bool:
        """Check if the API server is reachable."""
        import requests
        try:
            resp = requests.get(f"{self.api_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_for_result(self, task_id: str, poll_interval: float = 2.0, timeout: float = 600.0) -> str:
        import requests

        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.post(
                f"{self.api_url}/query_result",
                json={"task_ids": [task_id]},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json()
            task = results.get(task_id, {})
            status = task.get("status", 0)

            if status == 1:  # success
                return f"{self.api_url}/v1/audio?task_id={task_id}"
            elif status == 2:  # failed
                raise RuntimeError(f"Generation failed: {task.get('error', 'unknown error')}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def _cmd_generate(args):
    agent = MusicAgent(api_url=args.api_url)
    if not agent.health():
        print(f"ERROR: API server not reachable at {args.api_url}")
        print("Start it with: ./start_server.sh")
        sys.exit(1)

    print(f"Generating: {args.prompt!r}  [{args.duration}s]")
    result = agent.generate(
        prompt=args.prompt,
        lyrics=args.lyrics or "",
        duration=args.duration,
        bpm=args.bpm,
        key=args.key,
        output_path=args.output,
        audio_format=args.format,
        seed=args.seed,
    )
    print(f"Saved to: {result['path']}")


def _cmd_analyze(args):
    agent = MusicAgent(api_url=args.api_url)
    if not agent.health():
        print(f"ERROR: API server not reachable at {args.api_url}")
        sys.exit(1)

    result = agent.analyze(args.input)
    print(json.dumps(result, indent=2))


def _cmd_health(args):
    agent = MusicAgent(api_url=args.api_url)
    ok = agent.health()
    print("Server: OK" if ok else f"Server: UNREACHABLE ({args.api_url})")
    sys.exit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description="Music Agent - ACE-Step 1.5 wrapper")
    parser.add_argument("--api-url", default="http://localhost:7865", help="ACE-Step API server URL")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = sub.add_parser("generate", help="Generate music from a text prompt")
    gen.add_argument("--prompt", required=True, help="Music description")
    gen.add_argument("--lyrics", default="", help="Optional lyrics")
    gen.add_argument("--duration", type=int, default=60, help="Duration in seconds (10-600)")
    gen.add_argument("--bpm", type=int, default=None, help="Tempo hint")
    gen.add_argument("--key", default=None, help='Key hint, e.g. "C major"')
    gen.add_argument("--output", default="output.mp3", help="Output file path")
    gen.add_argument("--format", default="mp3", choices=["mp3", "flac", "wav", "aac", "opus", "wav32"])
    gen.add_argument("--seed", type=int, default=None, help="Reproducibility seed")
    gen.set_defaults(func=_cmd_generate)

    # analyze
    ana = sub.add_parser("analyze", help="Extract metadata from audio")
    ana.add_argument("--input", required=True, help="Path to audio file")
    ana.set_defaults(func=_cmd_analyze)

    # health
    hlt = sub.add_parser("health", help="Check API server health")
    hlt.set_defaults(func=_cmd_health)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
