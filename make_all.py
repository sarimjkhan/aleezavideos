#!/usr/bin/env python3
"""Make lots of quiz videos (shorts + long) from puzzle_bank.json.

  python3 make_all.py --shorts 5 --long 2      # a batch
  python3 make_all.py --daily                  # today's 1 short + 1 long (date-seeded, so it varies daily)
Videos land in videos/.
"""
import argparse, datetime, json, os, random
from make_video import render

TITLES = ["Guess the Word!", "Emoji Quiz!", "Can You Guess It?", "Emoji Riddles!", "What's the Word?"]


def make(bank, rnd, n, think, name_prefix, landscape, outdir, idx):
    ps = rnd.sample(bank, n)
    cfg = {"title": rnd.choice(TITLES), "subtitle": "Emoji + Emoji = ?",
           "think_seconds": think, "reveal_seconds": 2.5, "puzzles": ps}
    path = os.path.join(outdir, f"{name_prefix}_{idx:02d}.mp4")
    render(cfg, path, landscape)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shorts", type=int, default=0)
    ap.add_argument("--long", type=int, default=0)
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--bank", default="puzzle_bank.json")
    ap.add_argument("--out", default="videos")
    ap.add_argument("--tag", default=None, help="file-name tag (default: today's date for --daily)")
    a = ap.parse_args()
    bank = json.load(open(a.bank, encoding="utf-8"))["puzzles"]
    os.makedirs(a.out, exist_ok=True)
    if a.daily:
        a.shorts, a.long = 1, 1
        today = datetime.date.today().isoformat()
        a.tag = a.tag or today
        rnd = random.Random(today)
    else:
        rnd = random.Random()
        a.tag = a.tag or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for i in range(a.shorts):   # vertical, ~35s: 4 puzzles
        make(bank, rnd, 4, 4, f"short_{a.tag}", False, a.out, i + 1)
    for i in range(a.long):     # landscape, ~2.5min: 12 puzzles
        make(bank, rnd, 12, 4, f"long_{a.tag}", True, a.out, i + 1)


if __name__ == "__main__":
    main()
