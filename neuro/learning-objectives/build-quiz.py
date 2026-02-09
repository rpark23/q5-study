#!/usr/bin/env python3
"""
Build script: Parses quiz markdown files and generates a single self-contained HTML quiz app.
Usage: python3 build-quiz.py
"""

import os
import re
import json
import glob

QUIZ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quizzes")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiz-app.html")
COURSE_NAME = "INDE-223A Neuroscience Block"


def parse_quiz_file(filepath):
    """Parse a quiz markdown file into structured JSON data."""
    with open(filepath, "r") as f:
        content = f.read()

    filename = os.path.basename(filepath)

    # Extract number, slug, and type from filename like 01-topic-name-pre.md
    m = re.match(r"(\d+)-(.+)-(pre|post)\.md$", filename)
    if not m:
        return None
    number = m.group(1)
    slug = m.group(2)
    quiz_type = m.group(3)

    # Extract title from first H1
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else slug.replace("-", " ").title()

    # Split content at "## Answer Key" (with optional --- before it)
    ak_split = re.split(r"(?:^---\s*\n)?^##\s+Answer\s+Key\b", content, flags=re.MULTILINE)
    if len(ak_split) < 2:
        print(f"  WARNING: Could not find answer key in {filename}")
        return None
    question_section = ak_split[0]
    answer_section = ak_split[1]

    # ── Parse questions ──
    # Split on question headers. Handles both formats:
    #   Format A: **Q1.** text  or  **1.** text
    #   Format B: ### Q1. text
    q_blocks = re.split(
        r"\n(?=\s*(?:#{2,4}\s+)?(?:\*\*\s*)?Q?\d+[\.\)])",
        question_section,
    )

    questions = []
    for block in q_blocks:
        block = block.strip()
        if not block:
            continue

        # Match question number from various header formats
        num_match = re.match(
            r"(?:#{2,4}\s+)?(?:\*\*\s*)?Q?(\d+)[\.\)]\s*(?:\*\*)?\s*(.*)",
            block,
            re.DOTALL,
        )
        if not num_match:
            continue

        q_num = int(num_match.group(1))
        q_body = num_match.group(2).strip()

        # Extract options A-D. Handles:
        #   - A) text       (bullet style)
        #   A) text          (plain style)
        #   **A)** text      (bold style)
        opt_pattern = re.compile(
            r"(?:^|\n)\s*(?:[-*]\s+)?(?:\*\*)?([A-D])[\.\)]\s*(?:\*\*)?\s*(.+?)(?=\n\s*(?:[-*]\s+)?(?:\*\*)?[A-D][\.\)]|$)",
            re.DOTALL,
        )
        opt_matches = list(opt_pattern.finditer(q_body))

        if not opt_matches or len(opt_matches) < 2:
            continue

        q_text = q_body[: opt_matches[0].start()].strip()
        options = {}
        for om in opt_matches:
            letter = om.group(1)
            opt_text = om.group(2).strip()
            opt_text = re.sub(r"\*\*$", "", opt_text).strip()
            options[letter] = opt_text

        if len(options) < 2:
            continue

        questions.append(
            {
                "number": q_num,
                "text": clean_md(q_text),
                "options": options,
                "correct": None,
                "explanations": {},
            }
        )

    # ── Parse answer key ──
    ans_blocks = re.split(
        r"\n(?=\s*(?:#{2,4}\s+)?(?:\*\*\s*)?Q?\d+[\.\)])",
        answer_section,
    )

    for block in ans_blocks:
        block = block.strip()
        if not block:
            continue

        # Extract question number and correct answer
        ans_match = re.match(
            r"(?:#{2,4}\s+)?(?:\*\*\s*)?Q?(\d+)[\.\)]\s*(?:\*\*)?\s*[Aa]nswer[:\s]+\**\s*([A-D])\b",
            block,
        )
        if not ans_match:
            continue

        q_num = int(ans_match.group(1))
        correct = ans_match.group(2)

        q = next((q for q in questions if q["number"] == q_num), None)
        if not q:
            continue

        q["correct"] = correct

        # Extract per-option explanations (handles both - **A)** and - **A)** ... formats)
        expl_pattern = re.compile(
            r"[-*]\s*\**\s*([A-D])[\.\)]\s*(?:[^*]*?\*\*)?\s*(.+?)(?=\n[-*]\s*\**\s*[A-D][\.\)]|$)",
            re.DOTALL,
        )
        for em in expl_pattern.finditer(block):
            letter = em.group(1)
            expl = em.group(2).strip()
            expl = re.sub(r"\*\*", "", expl).strip()
            q["explanations"][letter] = expl

    valid_questions = [q for q in questions if q["correct"] is not None]

    if not valid_questions:
        print(f"  WARNING: No valid questions parsed from {filename}")
        return None

    return {
        "id": f"{number}-{slug}-{quiz_type}",
        "number": number,
        "slug": slug,
        "type": quiz_type,
        "title": title,
        "questions": valid_questions,
    }


def clean_md(text):
    """Light cleanup of markdown text for display."""
    text = text.strip()
    # Remove leading/trailing **
    text = re.sub(r"^\*\*|\*\*$", "", text)
    return text


def build_html(quizzes):
    """Generate the complete self-contained HTML quiz app."""
    quiz_json = json.dumps(quizzes, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{COURSE_NAME} — Quiz App</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {{
  --bg: #0c0f1a;
  --bg2: #111627;
  --bg3: #1a2038;
  --surface: #161b2e;
  --surface2: #1e2540;
  --surface3: #252d48;
  --border: rgba(255,255,255,0.06);
  --border2: rgba(255,255,255,0.1);
  --text: #eaf0ff;
  --text2: #8892b0;
  --text3: #5a6480;
  --accent: #64b5f6;
  --accent2: #42a5f5;
  --accent-glow: rgba(100,181,246,0.15);
  --correct: #66bb6a;
  --correct-bg: rgba(102,187,106,0.1);
  --correct-border: rgba(102,187,106,0.4);
  --incorrect-bg: rgba(120,144,156,0.08);
  --incorrect-border: rgba(120,144,156,0.2);
  --wrong: #ef5350;
  --wrong-bg: rgba(239,83,80,0.1);
  --wrong-border: rgba(239,83,80,0.4);
  --pre: #ffa726;
  --pre-soft: rgba(255,167,38,0.12);
  --post: #ab47bc;
  --post-soft: rgba(171,71,188,0.12);
  --radius: 12px;
  --radius-sm: 8px;
  --shadow: 0 1px 3px rgba(0,0,0,0.3), 0 4px 12px rgba(0,0,0,0.15);
  --shadow-lg: 0 4px 24px rgba(0,0,0,0.35);
  --transition: 0.2s cubic-bezier(0.4,0,0.2,1);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
  display: flex;
  height: 100vh;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
  line-height: 1.5;
}}

/* ── Sidebar ── */
.sidebar {{
  width: 300px;
  min-width: 300px;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
  scrollbar-color: var(--surface3) transparent;
}}
.sidebar::-webkit-scrollbar {{ width: 5px; }}
.sidebar::-webkit-scrollbar-thumb {{ background: var(--surface3); border-radius: 4px; }}
.sidebar-header {{
  padding: 24px 20px 16px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg2);
  z-index: 2;
  backdrop-filter: blur(12px);
}}
.sidebar-header h2 {{
  font-size: 14px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.sidebar-header .subtitle {{
  font-size: 12px;
  color: var(--text2);
  margin-top: 4px;
  font-weight: 500;
}}
.nav-home {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  transition: background var(--transition);
}}
.nav-home:hover {{ background: var(--surface); }}
.nav-home.active {{ background: var(--surface); color: var(--accent); }}
.nav-home svg {{ width:16px; height:16px; flex-shrink:0; }}
.nav-group {{ padding: 6px 0; }}
.nav-group-title {{
  font-size: 11px;
  font-weight: 700;
  color: var(--text3);
  padding: 12px 20px 6px;
  text-transform: uppercase;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.nav-group-title .num {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 5px;
  background: var(--surface2);
  font-size: 10px;
  font-weight: 800;
  color: var(--text2);
}}
.nav-item {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 20px 9px 28px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--text2);
  transition: all var(--transition);
  border-left: 3px solid transparent;
  position: relative;
}}
.nav-item:hover {{ background: var(--surface); color: var(--text); }}
.nav-item.active {{
  background: var(--accent-glow);
  border-left-color: var(--accent);
  color: var(--text);
}}
.badge {{
  font-size: 9px;
  font-weight: 700;
  padding: 3px 7px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  flex-shrink: 0;
}}
.badge-pre {{ background: var(--pre-soft); color: var(--pre); }}
.badge-post {{ background: var(--post-soft); color: var(--post); }}
.nav-check {{
  margin-left: auto;
  font-size: 11px;
  flex-shrink: 0;
  color: var(--correct);
  font-weight: 700;
}}

/* ── Main ── */
.main {{
  flex: 1;
  overflow-y: auto;
  background: var(--bg);
  scrollbar-width: thin;
  scrollbar-color: var(--surface3) transparent;
}}
.main::-webkit-scrollbar {{ width: 6px; }}
.main::-webkit-scrollbar-thumb {{ background: var(--surface3); border-radius: 4px; }}

/* ── Home ── */
.home {{ padding: 48px 32px 64px; max-width: 900px; margin: 0 auto; }}
.home-header {{ margin-bottom: 36px; }}
.home-header h1 {{
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, var(--text), var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 6px;
}}
.home-header .sub {{
  color: var(--text2);
  font-size: 15px;
  font-weight: 400;
}}

/* Stats strip */
.stats-strip {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 40px;
}}
.stat-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  text-align: center;
}}
.stat-card .stat-value {{
  font-size: 28px;
  font-weight: 800;
  color: var(--accent);
  line-height: 1;
  margin-bottom: 4px;
}}
.stat-card .stat-label {{
  font-size: 11px;
  font-weight: 600;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.8px;
}}
.stat-card .stat-bar {{
  height: 4px;
  background: var(--surface3);
  border-radius: 2px;
  margin-top: 12px;
  overflow: hidden;
}}
.stat-card .stat-bar-fill {{
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), var(--post));
  transition: width 0.6s ease;
}}

/* Lecture row */
.lecture-group {{
  margin-bottom: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: border-color var(--transition);
}}
.lecture-group:hover {{ border-color: var(--border2); }}
.lecture-row {{
  display: flex;
  align-items: stretch;
}}
.lecture-info {{
  flex: 1;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
}}
.lecture-num {{
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--surface3);
  font-size: 14px;
  font-weight: 800;
  color: var(--text2);
  flex-shrink: 0;
}}
.lecture-title {{
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.35;
}}
.lecture-actions {{
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
}}
.quiz-btn {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px 22px;
  cursor: pointer;
  border: none;
  background: transparent;
  color: var(--text2);
  font-family: inherit;
  transition: all var(--transition);
  border-left: 1px solid var(--border);
  min-width: 90px;
}}
.quiz-btn:hover {{ background: var(--surface2); color: var(--text); }}
.quiz-btn .quiz-btn-badge {{ margin-bottom: 0; }}
.quiz-btn .quiz-btn-meta {{
  font-size: 10px;
  font-weight: 500;
  color: var(--text3);
}}
.quiz-btn .quiz-btn-check {{
  font-size: 10px;
  color: var(--correct);
  font-weight: 600;
}}

/* ── Quiz view ── */
.quiz-container {{
  max-width: 780px;
  margin: 0 auto;
  padding: 0 24px 64px;
}}

/* Sticky header */
.quiz-top {{
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--bg);
  padding: 20px 0 16px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 28px;
}}
.quiz-top-inner {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}}
.back-btn {{
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text2);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--transition);
  font-size: 16px;
}}
.back-btn:hover {{ background: var(--surface2); color: var(--text); border-color: var(--border2); }}
.quiz-top h1 {{
  font-size: 20px;
  font-weight: 700;
  flex: 1;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.quiz-top .meta {{
  font-size: 12px;
  color: var(--text3);
  font-weight: 500;
}}
.progress-wrap {{
  background: var(--surface);
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
}}
.progress-bar {{
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #ab47bc);
  border-radius: 4px;
  transition: width 0.5s cubic-bezier(0.4,0,0.2,1);
  width: 0%;
}}

/* Question dots */
.q-dots {{
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}}
.q-dot {{
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: all var(--transition);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text3);
}}
.q-dot:hover {{ border-color: var(--accent); color: var(--text); }}
.q-dot.current {{ border-color: var(--accent); color: var(--accent); background: var(--accent-glow); }}
.q-dot.correct {{ background: var(--correct-bg); border-color: var(--correct-border); color: var(--correct); }}
.q-dot.wrong {{ background: var(--wrong-bg); border-color: var(--wrong-border); color: var(--wrong); }}
.q-dot.revealed {{ background: var(--incorrect-bg); border-color: var(--incorrect-border); color: var(--text3); }}

/* Question card */
.q-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
  margin-bottom: 16px;
  transition: border-color var(--transition), opacity var(--transition);
}}
.q-card:hover {{ border-color: var(--border2); }}
.q-card.answered {{ opacity: 0.85; }}
.q-card.answered:hover {{ opacity: 1; }}
.q-card.active-q {{ border-color: var(--accent); border-width: 1px; }}
.q-number {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 12px;
}}
.q-number .q-num-circle {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--accent-glow);
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}}
.q-text {{
  font-size: 15px;
  line-height: 1.65;
  margin-bottom: 20px;
  color: var(--text);
  font-weight: 400;
}}
.options {{ display: flex; flex-direction: column; gap: 8px; }}
.option-btn {{
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: var(--surface2);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1.55;
  color: var(--text);
  text-align: left;
  transition: all var(--transition);
  width: 100%;
  font-family: inherit;
}}
.option-btn:hover:not(.locked) {{
  border-color: var(--accent);
  background: var(--accent-glow);
  transform: translateX(4px);
}}
.option-btn .letter {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--surface3);
  font-weight: 700;
  font-size: 12px;
  color: var(--text2);
  flex-shrink: 0;
  transition: all var(--transition);
}}
.option-btn:hover:not(.locked) .letter {{ background: var(--accent); color: var(--bg); }}
.option-btn.locked {{ cursor: default; }}
.option-btn.correct-pick {{
  border-color: var(--correct-border);
  background: var(--correct-bg);
}}
.option-btn.correct-pick .letter {{ background: var(--correct); color: #fff; }}
.option-btn.wrong-pick {{
  border-color: var(--wrong-border);
  background: var(--wrong-bg);
}}
.option-btn.wrong-pick .letter {{ background: var(--wrong); color: #fff; }}
.option-btn.correct-reveal {{
  border-color: var(--correct-border);
  background: var(--correct-bg);
}}
.option-btn.correct-reveal .letter {{ background: var(--correct); color: #fff; }}
.option-btn.incorrect-reveal {{
  background: var(--incorrect-bg);
  border-color: var(--border);
  opacity: 0.7;
}}

/* Explanation */
.explanation {{
  margin-top: 6px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.6;
  display: none;
  animation: fadeSlideIn 0.25s ease;
}}
@keyframes fadeSlideIn {{
  from {{ opacity:0; transform: translateY(-4px); }}
  to {{ opacity:1; transform: translateY(0); }}
}}
.explanation.show {{ display: block; }}
.explanation.correct-expl {{
  background: var(--correct-bg);
  border-left: 3px solid var(--correct);
  color: #c8e6c9;
}}
.explanation.incorrect-expl {{
  background: var(--incorrect-bg);
  border-left: 3px solid var(--incorrect-border);
  color: var(--text2);
}}
.explanation.wrong-expl {{
  background: var(--wrong-bg);
  border-left: 3px solid var(--wrong);
  color: #ffcdd2;
}}

/* Reveal button */
.reveal-btn {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 10px 18px;
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: var(--radius-sm);
  color: var(--text2);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all var(--transition);
}}
.reveal-btn:hover {{
  background: var(--surface3);
  border-color: var(--accent);
  color: var(--accent);
}}
.reveal-btn svg {{ width:14px; height:14px; flex-shrink:0; }}

/* ── Results ── */
.results {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 40px 32px;
  text-align: center;
  margin-top: 32px;
  box-shadow: var(--shadow-lg);
}}
.results h2 {{
  font-size: 24px;
  font-weight: 800;
  margin-bottom: 8px;
}}
.results .results-subtitle {{
  font-size: 14px;
  color: var(--text2);
  margin-bottom: 28px;
}}
.score-ring {{
  width: 160px;
  height: 160px;
  margin: 0 auto 24px;
  position: relative;
}}
.score-ring svg {{ transform: rotate(-90deg); }}
.score-ring .label {{
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}}
.score-ring .pct {{ font-size: 36px; font-weight: 800; }}
.score-ring .sub {{ font-size: 13px; color: var(--text2); font-weight: 500; }}
.stat-row {{
  display: flex;
  justify-content: center;
  gap: 28px;
  margin: 20px 0 28px;
}}
.stat-item {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}}
.stat-item .stat-num {{ font-size: 20px; font-weight: 700; color: var(--text); }}
.stat-item .stat-lbl {{ font-size: 11px; font-weight: 600; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; }}
.btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 28px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  border: none;
  transition: all var(--transition);
  margin: 4px;
}}
.btn-primary {{
  background: var(--accent);
  color: var(--bg);
}}
.btn-primary:hover {{ background: var(--accent2); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(100,181,246,0.3); }}
.btn-secondary {{
  background: var(--surface2);
  color: var(--text);
  border: 1px solid var(--border2);
}}
.btn-secondary:hover {{ background: var(--surface3); transform: translateY(-1px); }}

/* ── Scroll-to-top ── */
.scroll-top {{
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--surface2);
  border: 1px solid var(--border2);
  color: var(--text2);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition: all var(--transition);
  z-index: 50;
  box-shadow: var(--shadow);
}}
.scroll-top.visible {{ opacity: 1; pointer-events: auto; }}
.scroll-top:hover {{ background: var(--accent); color: var(--bg); border-color: var(--accent); }}

/* ── Mobile ── */
.hamburger {{
  display: none;
  position: fixed;
  top: 14px;
  left: 14px;
  z-index: 100;
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  cursor: pointer;
  color: var(--text);
  font-size: 18px;
  box-shadow: var(--shadow);
  line-height: 1;
}}
.sidebar-overlay {{
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  z-index: 9;
}}
@media (max-width: 860px) {{
  .sidebar {{
    position: fixed;
    left: -320px;
    top: 0;
    bottom: 0;
    z-index: 10;
    transition: left 0.3s cubic-bezier(0.4,0,0.2,1);
    width: 300px;
    box-shadow: var(--shadow-lg);
  }}
  .sidebar.open {{ left: 0; }}
  .sidebar-overlay.open {{ display: block; }}
  .hamburger {{ display: flex; align-items: center; justify-content: center; }}
  .main {{ width: 100%; }}
  .quiz-container {{ padding: 0 16px 48px; }}
  .quiz-top {{ padding: 16px 0 12px; }}
  .home {{ padding: 64px 16px 48px; }}
  .stats-strip {{ grid-template-columns: 1fr; gap: 10px; }}
  .lecture-row {{ flex-direction: column; }}
  .lecture-actions {{ border-top: 1px solid var(--border); }}
  .quiz-btn {{ border-left: none !important; flex: 1; padding: 10px; }}
  .q-dots {{ display: none; }}
  .stat-row {{ flex-wrap: wrap; gap: 16px; }}
}}
@media (max-width: 480px) {{
  .home-header h1 {{ font-size: 24px; }}
  .q-card {{ padding: 20px 16px; }}
  .quiz-top h1 {{ font-size: 16px; }}
}}
</style>
</head>
<body>

<button class="hamburger" onclick="toggleSidebar()" aria-label="Menu">&#9776;</button>
<div class="sidebar-overlay" onclick="toggleSidebar()"></div>

<nav class="sidebar">
  <div class="sidebar-header">
    <h2>{COURSE_NAME}</h2>
    <div class="subtitle">Interactive Quiz App</div>
  </div>
  <div id="sidebar-nav"></div>
</nav>

<div class="main" id="main">
  <div class="home" id="home-view"></div>
  <div class="quiz-container" id="quiz-view" style="display:none"></div>
</div>

<button class="scroll-top" id="scrollTop" onclick="document.getElementById('main').scrollTo({{top:0,behavior:'smooth'}})">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 15l-6-6-6 6"/></svg>
</button>

<script>
const QUIZZES = {quiz_json};

let currentQuiz = null;
let answers = {{}};
let completedQuizzes = JSON.parse(localStorage.getItem('neuroQuizCompleted') || '{{}}');
let bestScores = JSON.parse(localStorage.getItem('neuroQuizBest') || '{{}}');

function groupByLecture() {{
  const g = {{}};
  QUIZZES.forEach(q => {{ if (!g[q.number]) g[q.number] = []; g[q.number].push(q); }});
  return g;
}}

// ── Sidebar ──
function buildSidebar() {{
  const nav = document.getElementById('sidebar-nav');
  const groups = groupByLecture();
  let html = `<div class="nav-home" onclick="showHome()" id="nav-home">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12l9-9 9 9"/><path d="M9 21V9h6v12"/></svg>
    Home
  </div>`;
  for (const [num, quizzes] of Object.entries(groups).sort((a,b) => a[0]-b[0])) {{
    const title = quizzes[0].title.replace(/ — (Pre|Post)-Quiz$/, '');
    html += `<div class="nav-group"><div class="nav-group-title"><span class="num">${{num}}</span>${{truncate(title,28)}}</div>`;
    quizzes.sort((a,b) => a.type === 'pre' ? -1 : 1).forEach(q => {{
      const badge = q.type === 'pre' ? '<span class="badge badge-pre">PRE</span>' : '<span class="badge badge-post">POST</span>';
      const check = completedQuizzes[q.id] ? '<span class="nav-check">&#10003;</span>' : '';
      html += `<div class="nav-item" data-id="${{q.id}}" onclick="loadQuiz('${{q.id}}')">${{badge}}<span style="flex:1">${{q.type==='pre'?'Pre-Quiz':'Post-Quiz'}}</span>${{check}}</div>`;
    }});
    html += '</div>';
  }}
  nav.innerHTML = html;
}}

function highlightNav(id) {{
  document.querySelectorAll('.nav-item, .nav-home').forEach(el => el.classList.remove('active'));
  if (id === null) document.getElementById('nav-home')?.classList.add('active');
  else document.querySelector(`.nav-item[data-id="${{id}}"]`)?.classList.add('active');
}}

// ── Home ──
function showHome() {{
  document.getElementById('home-view').style.display = '';
  document.getElementById('quiz-view').style.display = 'none';
  currentQuiz = null;
  highlightNav(null);
  closeSidebar();

  const groups = groupByLecture();
  const totalQuizzes = QUIZZES.length;
  const doneCount = Object.keys(completedQuizzes).length;
  const totalQs = QUIZZES.reduce((s,q) => s + q.questions.length, 0);
  const avgScore = Object.values(bestScores).length
    ? Math.round(Object.values(bestScores).reduce((a,b)=>a+b,0) / Object.values(bestScores).length)
    : 0;

  let html = `<div class="home-header"><h1>{COURSE_NAME}</h1><p class="sub">Test your knowledge across 8 lectures</p></div>`;

  html += `<div class="stats-strip">
    <div class="stat-card"><div class="stat-value">${{doneCount}}/${{totalQuizzes}}</div><div class="stat-label">Quizzes Completed</div><div class="stat-bar"><div class="stat-bar-fill" style="width:${{totalQuizzes?Math.round(doneCount/totalQuizzes*100):0}}%"></div></div></div>
    <div class="stat-card"><div class="stat-value">${{totalQs}}</div><div class="stat-label">Total Questions</div><div class="stat-bar"><div class="stat-bar-fill" style="width:100%"></div></div></div>
    <div class="stat-card"><div class="stat-value">${{avgScore}}%</div><div class="stat-label">Average Best Score</div><div class="stat-bar"><div class="stat-bar-fill" style="width:${{avgScore}}%"></div></div></div>
  </div>`;

  for (const [num, quizzes] of Object.entries(groups).sort((a,b) => a[0]-b[0])) {{
    const title = quizzes[0].title.replace(/ — (Pre|Post)-Quiz$/, '');
    html += `<div class="lecture-group"><div class="lecture-row"><div class="lecture-info"><div class="lecture-num">${{num}}</div><div class="lecture-title">${{title}}</div></div><div class="lecture-actions">`;
    quizzes.sort((a,b) => a.type==='pre'?-1:1).forEach(q => {{
      const badge = q.type==='pre' ? '<span class="badge badge-pre quiz-btn-badge">PRE</span>' : '<span class="badge badge-post quiz-btn-badge">POST</span>';
      const best = bestScores[q.id] !== undefined ? `<span class="quiz-btn-check">${{bestScores[q.id]}}%</span>` : `<span class="quiz-btn-meta">${{q.questions.length}} Qs</span>`;
      html += `<button class="quiz-btn" onclick="loadQuiz('${{q.id}}')">${{badge}}${{best}}</button>`;
    }});
    html += `</div></div></div>`;
  }}

  document.getElementById('home-view').innerHTML = html;
}}

// ── Quiz ──
function loadQuiz(id) {{
  const quiz = QUIZZES.find(q => q.id === id);
  if (!quiz) return;
  currentQuiz = quiz;
  answers = {{}};
  quiz.questions.forEach((_,i) => {{ answers[i] = {{ picked: null, revealed: false }}; }});
  document.getElementById('home-view').style.display = 'none';
  document.getElementById('quiz-view').style.display = '';
  highlightNav(id);
  closeSidebar();
  renderQuiz();
  document.getElementById('main').scrollTo(0, 0);
}}

function renderQuiz() {{
  const q = currentQuiz;
  const total = q.questions.length;
  const done = Object.values(answers).filter(a => a.picked || a.revealed).length;
  const pct = total ? Math.round(done / total * 100) : 0;

  const typeBadge = q.type === 'pre'
    ? '<span class="badge badge-pre" style="font-size:10px">PRE</span>'
    : '<span class="badge badge-post" style="font-size:10px">POST</span>';

  let html = `<div class="quiz-top">
    <div class="quiz-top-inner">
      <button class="back-btn" onclick="showHome()" title="Back to Home">&larr;</button>
      <h1>${{q.title}}</h1>
      ${{typeBadge}}
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <div class="progress-wrap" style="flex:1"><div class="progress-bar" style="width:${{pct}}%"></div></div>
      <span class="meta">${{done}}/${{total}}</span>
    </div>
  </div>`;

  // Question dots
  html += '<div class="q-dots">';
  q.questions.forEach((question, idx) => {{
    const a = answers[idx];
    let cls = 'q-dot';
    if (a.picked) cls += a.picked === question.correct ? ' correct' : ' wrong';
    else if (a.revealed) cls += ' revealed';
    html += `<div class="${{cls}}" onclick="scrollToQ(${{idx}})">${{idx+1}}</div>`;
  }});
  html += '</div>';

  q.questions.forEach((question, idx) => {{
    const a = answers[idx];
    const isAnswered = a.picked !== null || a.revealed;
    html += `<div class="q-card ${{isAnswered ? 'answered' : ''}}" id="q${{idx}}">`;
    html += `<div class="q-number"><span class="q-num-circle">${{idx+1}}</span>Question ${{idx+1}} of ${{total}}</div>`;
    html += `<div class="q-text">${{escHtml(question.text)}}</div>`;
    html += '<div class="options">';

    ['A','B','C','D'].forEach(letter => {{
      if (!question.options[letter]) return;
      let cls = 'option-btn';
      if (isAnswered) {{
        cls += ' locked';
        if (letter === question.correct) cls += a.picked === letter ? ' correct-pick' : ' correct-reveal';
        else if (a.picked === letter) cls += ' wrong-pick';
        else cls += ' incorrect-reveal';
      }}
      const onclick = isAnswered ? '' : `onclick="pickAnswer(${{idx}},'${{letter}}')"`;
      html += `<button class="${{cls}}" ${{onclick}}><span class="letter">${{letter}}</span><span>${{escHtml(question.options[letter])}}</span></button>`;
      if (isAnswered && question.explanations[letter]) {{
        let explCls = 'explanation show ';
        if (letter === question.correct) explCls += 'correct-expl';
        else if (a.picked === letter) explCls += 'wrong-expl';
        else explCls += 'incorrect-expl';
        html += `<div class="${{explCls}}">${{escHtml(question.explanations[letter])}}</div>`;
      }}
    }});

    html += '</div>';
    if (!isAnswered) {{
      html += `<button class="reveal-btn" onclick="revealAnswer(${{idx}})">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><circle cx="12" cy="17" r="0.5"/></svg>
        I Don't Know &mdash; Show Answer</button>`;
    }}
    html += '</div>';
  }});

  if (done === total && total > 0) html += buildResults();
  document.getElementById('quiz-view').innerHTML = html;
}}

function scrollToQ(idx) {{
  document.getElementById('q'+idx)?.scrollIntoView({{ behavior:'smooth', block:'center' }});
}}

function pickAnswer(idx, letter) {{
  if (answers[idx].picked || answers[idx].revealed) return;
  answers[idx].picked = letter;
  renderQuiz();
  setTimeout(() => document.getElementById('q'+idx)?.scrollIntoView({{ behavior:'smooth', block:'nearest' }}), 50);
}}

function revealAnswer(idx) {{
  if (answers[idx].picked || answers[idx].revealed) return;
  answers[idx].revealed = true;
  renderQuiz();
  setTimeout(() => document.getElementById('q'+idx)?.scrollIntoView({{ behavior:'smooth', block:'nearest' }}), 50);
}}

function buildResults() {{
  const q = currentQuiz;
  const total = q.questions.length;
  let attempted = 0, correct = 0, revealed = 0;
  Object.entries(answers).forEach(([idx, a]) => {{
    if (a.picked) {{ attempted++; if (a.picked === q.questions[idx].correct) correct++; }}
    else if (a.revealed) revealed++;
  }});
  const pct = attempted > 0 ? Math.round(correct / attempted * 100) : 0;
  const missed = Object.entries(answers).filter(([idx, a]) =>
    (a.picked && a.picked !== q.questions[idx].correct) || a.revealed
  ).length;

  completedQuizzes[q.id] = true;
  if (!bestScores[q.id] || pct > bestScores[q.id]) bestScores[q.id] = pct;
  localStorage.setItem('neuroQuizCompleted', JSON.stringify(completedQuizzes));
  localStorage.setItem('neuroQuizBest', JSON.stringify(bestScores));
  buildSidebar();
  highlightNav(q.id);

  const r = 64, c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  const color = pct >= 80 ? 'var(--correct)' : pct >= 60 ? 'var(--pre)' : 'var(--wrong)';
  const grade = pct >= 90 ? 'Excellent!' : pct >= 80 ? 'Great job!' : pct >= 70 ? 'Good effort!' : pct >= 60 ? 'Keep studying!' : 'Review this material';

  let html = `<div class="results"><h2>Quiz Complete!</h2><p class="results-subtitle">${{grade}}</p>`;
  html += `<div class="score-ring"><svg width="160" height="160"><circle cx="80" cy="80" r="${{r}}" fill="none" stroke="var(--surface3)" stroke-width="8"/><circle cx="80" cy="80" r="${{r}}" fill="none" stroke="${{color}}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${{c}}" stroke-dashoffset="${{offset}}" style="transition:stroke-dashoffset 0.8s cubic-bezier(0.4,0,0.2,1)"/></svg><div class="label"><div class="pct" style="color:${{color}}">${{pct}}%</div><div class="sub">${{correct}}/${{attempted}}</div></div></div>`;
  html += `<div class="stat-row">
    <div class="stat-item"><div class="stat-num">${{attempted}}</div><div class="stat-lbl">Attempted</div></div>
    <div class="stat-item"><div class="stat-num">${{correct}}</div><div class="stat-lbl">Correct</div></div>
    <div class="stat-item"><div class="stat-num">${{revealed}}</div><div class="stat-lbl">Revealed</div></div>
    <div class="stat-item"><div class="stat-num">${{missed}}</div><div class="stat-lbl">Missed</div></div>
  </div>`;
  if (missed > 0) html += `<button class="btn btn-secondary" onclick="reviewMissed()">Review Missed</button>`;
  html += `<button class="btn btn-primary" onclick="loadQuiz('${{q.id}}')">Retry Quiz</button>`;

  // Next quiz button
  const curIdx = QUIZZES.findIndex(x => x.id === q.id);
  if (curIdx < QUIZZES.length - 1) {{
    const next = QUIZZES[curIdx + 1];
    html += `<button class="btn btn-secondary" onclick="loadQuiz('${{next.id}}')" style="margin-top:8px">Next Quiz &rarr;</button>`;
  }}
  html += '</div>';
  return html;
}}

function reviewMissed() {{
  const q = currentQuiz;
  for (let i = 0; i < q.questions.length; i++) {{
    const a = answers[i];
    if ((a.picked && a.picked !== q.questions[i].correct) || a.revealed) {{
      document.getElementById('q'+i)?.scrollIntoView({{ behavior:'smooth', block:'start' }});
      return;
    }}
  }}
}}

function escHtml(s) {{ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}
function truncate(s, n) {{ return s.length > n ? s.slice(0, n) + '...' : s; }}

function toggleSidebar() {{
  document.querySelector('.sidebar').classList.toggle('open');
  document.querySelector('.sidebar-overlay').classList.toggle('open');
}}
function closeSidebar() {{
  document.querySelector('.sidebar').classList.remove('open');
  document.querySelector('.sidebar-overlay').classList.remove('open');
}}

// Scroll-to-top button visibility
document.getElementById('main').addEventListener('scroll', function() {{
  document.getElementById('scrollTop').classList.toggle('visible', this.scrollTop > 400);
}});

// Keyboard navigation
document.addEventListener('keydown', e => {{
  if (!currentQuiz) return;
  const total = currentQuiz.questions.length;
  const done = Object.values(answers).filter(a => a.picked || a.revealed).length;
  // Find first unanswered
  if (['a','b','c','d'].includes(e.key.toLowerCase()) && !e.ctrlKey && !e.metaKey) {{
    for (let i = 0; i < total; i++) {{
      if (!answers[i].picked && !answers[i].revealed) {{
        pickAnswer(i, e.key.toUpperCase());
        break;
      }}
    }}
  }}
}});

buildSidebar();
showHome();
</script>
</body>
</html>"""
    return html


def main():
    print(f"Scanning {QUIZ_DIR} for quiz files...")
    files = sorted(glob.glob(os.path.join(QUIZ_DIR, "*.md")))
    print(f"Found {len(files)} markdown files")

    quizzes = []
    for f in files:
        print(f"  Parsing: {os.path.basename(f)}")
        q = parse_quiz_file(f)
        if q:
            print(f"    -> {len(q['questions'])} questions parsed")
            quizzes.append(q)
        else:
            print(f"    -> SKIPPED (parse failed)")

    print(f"\nTotal quizzes: {len(quizzes)}")
    total_q = sum(len(q['questions']) for q in quizzes)
    print(f"Total questions: {total_q}")

    html = build_html(quizzes)
    with open(OUTPUT, "w") as f:
        f.write(html)
    print(f"\nGenerated: {OUTPUT}")
    print(f"File size: {len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
