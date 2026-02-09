#!/usr/bin/env python3
"""Parse quiz markdown files and generate an interactive HTML quiz app."""

import re
import json
import glob
import os

QUIZ_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(QUIZ_DIR, "quiz-app.html")


def parse_quiz_file(filepath):
    """Parse a markdown quiz file into structured data."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Extract title from first heading
    title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else os.path.basename(filepath)

    # Extract subtitle/lecture info
    subtitle_match = re.search(r'^###?\s+(?:Lecture:?\s*)?(.+)', content, re.MULTILINE)
    subtitle = subtitle_match.group(1).strip() if subtitle_match else ""

    # Find answer key section
    answer_key_match = re.search(r'##\s*Answer\s*Key', content, re.IGNORECASE)
    answer_key_text = content[answer_key_match.start():] if answer_key_match else ""

    # Try new per-option format first: ### Q1. Answer: B
    answers = {}
    new_format_blocks = re.split(r'###\s*Q(\d+)\.\s*Answer:\s*([A-D])', answer_key_text)

    if len(new_format_blocks) > 1:
        # new_format_blocks: ['preamble', '1', 'B', 'block text', '2', 'C', 'block text', ...]
        i = 1
        while i < len(new_format_blocks) - 2:
            qnum = int(new_format_blocks[i])
            correct = new_format_blocks[i + 1]
            block = new_format_blocks[i + 2]

            option_explanations = {}
            for opt_match in re.finditer(
                r'-\s*\*\*([A-D])\)\*\*\s*((?:Correct|Incorrect)[.\s]*)(.*?)(?=\n\s*-\s*\*\*[A-D]\)|\Z)',
                block, re.DOTALL
            ):
                letter = opt_match.group(1)
                status = opt_match.group(2).strip().rstrip('.')
                explanation = opt_match.group(3).strip()
                option_explanations[letter] = {
                    'status': status,
                    'text': explanation
                }

            answers[qnum] = {
                'correct': correct,
                'explanation': '',
                'option_explanations': option_explanations
            }
            i += 3

    # Fallback: old table format
    if not answers:
        answer_pattern = re.finditer(
            r'\|\s*Q?(\d+)\s*\|\s*\*?\*?([A-D])\*?\*?\s*\|\s*(.+?)\s*\|',
            content
        )
        for m in answer_pattern:
            qnum = int(m.group(1))
            answers[qnum] = {
                'correct': m.group(2),
                'explanation': m.group(3).strip(),
                'option_explanations': {}
            }

    # Parse questions
    questions = []
    q_pattern = re.finditer(
        r'\*\*Q(\d+)\.\*\*\s*(.+?)(?=\n\s*-\s*[A-D]\))',
        content, re.DOTALL
    )

    for qm in q_pattern:
        qnum = int(qm.group(1))
        question_text = qm.group(2).strip()

        q_start = qm.end()
        next_q = re.search(r'\*\*Q\d+\.\*\*', content[q_start:])
        answer_section = re.search(r'##\s*Answer\s*Key', content[q_start:], re.IGNORECASE)

        if next_q and answer_section:
            end = q_start + min(next_q.start(), answer_section.start())
        elif next_q:
            end = q_start + next_q.start()
        elif answer_section:
            end = q_start + answer_section.start()
        else:
            end = len(content)

        options_text = content[q_start:end]

        options = {}
        for opt_match in re.finditer(
            r'-\s*([A-D])\)\s*(.+?)(?=\n\s*-\s*[A-D]\)|\n\s*---|\n\s*\*\*Q|\n\s*##|\Z)',
            options_text, re.DOTALL
        ):
            letter = opt_match.group(1)
            opt_text = opt_match.group(2).strip()
            options[letter] = opt_text

        if len(options) >= 2:
            answer_info = answers.get(qnum, {})
            questions.append({
                'number': qnum,
                'question': question_text,
                'options': options,
                'correct': answer_info.get('correct', ''),
                'explanation': answer_info.get('explanation', ''),
                'option_explanations': answer_info.get('option_explanations', {})
            })

    return {
        'title': title,
        'subtitle': subtitle,
        'filename': os.path.basename(filepath),
        'questions': questions
    }


def generate_html(quizzes):
    """Generate the interactive HTML quiz app."""
    quiz_data_json = json.dumps(quizzes, indent=2)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hematology Quiz App</title>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --surface2: #334155;
    --border: #475569;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --accent: #818cf8;
    --accent-hover: #a5b4fc;
    --correct: #34d399;
    --correct-bg: rgba(52,211,153,0.12);
    --wrong: #f87171;
    --wrong-bg: rgba(248,113,113,0.12);
    --yellow: #fbbf24;
    --yellow-bg: rgba(251,191,36,0.12);
    --reveal: #60a5fa;
    --reveal-bg: rgba(96,165,250,0.12);
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }}
  .app {{ display: flex; min-height: 100vh; }}

  .sidebar {{
    width: 300px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 24px 16px;
    overflow-y: auto;
    flex-shrink: 0;
    position: fixed;
    top: 0; left: 0; height: 100vh;
  }}
  .sidebar h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; color: var(--accent); }}
  .sidebar .tagline {{ font-size: 12px; color: var(--text-dim); margin-bottom: 20px; }}
  .quiz-btn {{
    display: block; width: 100%; text-align: left;
    padding: 8px 14px; margin-bottom: 2px;
    background: transparent; border: 1px solid transparent;
    border-radius: 8px; color: var(--text); font-size: 13px;
    cursor: pointer; transition: all 0.15s; line-height: 1.4;
  }}
  .quiz-btn:hover {{ background: var(--surface2); }}
  .quiz-btn.active {{ background: var(--surface2); border-color: var(--accent); }}
  .quiz-btn .q-count {{ display: inline-block; font-size: 11px; color: var(--text-dim); margin-left: 6px; }}

  .lecture-header {{
    font-size: 11px; font-weight: 700; color: var(--text-dim);
    padding: 12px 14px 4px; margin-top: 4px; letter-spacing: 0.3px; line-height: 1.4;
  }}
  .lecture-divider {{ border-top: 1px solid var(--border); margin-top: 8px; }}
  .badge {{
    display: inline-block; padding: 1px 5px; border-radius: 3px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.5px; vertical-align: middle; margin-right: 4px;
  }}
  .badge-pre {{ background: rgba(251,191,36,0.15); color: var(--yellow); }}
  .badge-post {{ background: rgba(52,211,153,0.15); color: var(--correct); }}

  .main {{ margin-left: 300px; flex: 1; padding: 32px 40px; max-width: 860px; }}
  .quiz-header {{ margin-bottom: 28px; }}
  .quiz-header h2 {{ font-size: 24px; font-weight: 700; margin-bottom: 4px; }}
  .quiz-header .meta {{ font-size: 13px; color: var(--text-dim); }}
  .quiz-type-badge {{
    display: inline-block; padding: 3px 10px; border-radius: 4px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 8px;
  }}
  .quiz-type-badge.pre-badge {{ background: rgba(251,191,36,0.15); color: var(--yellow); }}
  .quiz-type-badge.post-badge {{ background: rgba(52,211,153,0.15); color: var(--correct); }}

  .progress-bar {{ height: 6px; background: var(--surface2); border-radius: 3px; margin-bottom: 28px; overflow: hidden; }}
  .progress-fill {{ height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.3s ease; }}

  .score-bar {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 20px; font-size: 14px; color: var(--text-dim);
  }}
  .score-bar .score {{ font-weight: 600; color: var(--text); }}

  .question-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px 28px; margin-bottom: 20px;
    transition: border-color 0.2s;
  }}
  .question-card.answered-correct {{ border-color: var(--correct); }}
  .question-card.answered-wrong {{ border-color: var(--wrong); }}
  .question-card.answered-reveal {{ border-color: var(--reveal); }}
  .q-number {{ font-size: 12px; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
  .q-text {{ font-size: 15px; line-height: 1.6; margin-bottom: 16px; }}

  .options {{ display: flex; flex-direction: column; gap: 8px; }}
  .option-btn {{
    display: flex; align-items: flex-start; gap: 12px;
    padding: 12px 16px; background: var(--bg);
    border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); font-size: 14px; line-height: 1.5;
    cursor: pointer; transition: all 0.15s; text-align: left;
  }}
  .option-btn:hover:not(.disabled) {{ border-color: var(--accent); background: var(--surface2); }}
  .option-btn .letter {{
    flex-shrink: 0; width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 6px; font-weight: 600; font-size: 13px;
    background: var(--surface2); transition: all 0.15s;
  }}
  .option-btn.selected .letter {{ background: var(--accent); color: var(--bg); }}
  .option-btn.correct {{ border-color: var(--correct); background: var(--correct-bg); opacity: 1 !important; }}
  .option-btn.correct .letter {{ background: var(--correct); color: var(--bg); }}
  .option-btn.wrong {{ border-color: var(--wrong); background: var(--wrong-bg); }}
  .option-btn.wrong .letter {{ background: var(--wrong); color: var(--bg); }}
  .option-btn.disabled {{ cursor: default; opacity: 0.6; }}
  .option-btn.disabled.correct {{ opacity: 1; }}

  /* Per-option explanations */
  .opt-explanation {{
    margin-top: 6px; padding: 8px 12px; border-radius: 6px;
    font-size: 12px; line-height: 1.5; display: none;
  }}
  .opt-explanation.show {{ display: block; }}
  .opt-explanation.opt-correct {{
    background: var(--correct-bg); color: var(--correct); border: 1px solid rgba(52,211,153,0.25);
  }}
  .opt-explanation.opt-wrong {{
    background: var(--surface2); color: var(--text-dim); border: 1px solid var(--border);
  }}

  /* Reveal button */
  .reveal-btn {{
    display: flex; align-items: center; justify-content: center; gap: 8px;
    width: 100%; padding: 10px 16px; margin-top: 10px;
    background: transparent; border: 1px dashed var(--border);
    border-radius: 8px; color: var(--text-dim); font-size: 13px;
    cursor: pointer; transition: all 0.15s;
  }}
  .reveal-btn:hover {{ border-color: var(--yellow); color: var(--yellow); background: var(--yellow-bg); }}
  .reveal-btn.hidden {{ display: none; }}
  .reveal-btn .icon {{ font-size: 16px; }}

  /* General explanation fallback */
  .explanation {{
    margin-top: 12px; padding: 14px 16px; border-radius: 8px;
    font-size: 13px; line-height: 1.6; display: none;
  }}
  .explanation.show {{ display: block; }}
  .explanation.correct-exp {{ background: var(--correct-bg); border: 1px solid var(--correct); color: var(--correct); }}
  .explanation.wrong-exp {{ background: var(--wrong-bg); border: 1px solid var(--wrong); color: var(--wrong); }}
  .explanation.reveal-exp {{ background: var(--reveal-bg); border: 1px solid var(--reveal); color: var(--reveal); }}
  .explanation .exp-label {{ font-weight: 700; margin-bottom: 4px; }}

  .results {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 32px; text-align: center; margin-top: 20px;
  }}
  .results h3 {{ font-size: 28px; margin-bottom: 8px; }}
  .results .pct {{ font-size: 48px; font-weight: 800; margin: 12px 0; }}
  .results .pct.great {{ color: var(--correct); }}
  .results .pct.ok {{ color: var(--yellow); }}
  .results .pct.needs-work {{ color: var(--wrong); }}
  .results .detail {{ color: var(--text-dim); font-size: 14px; margin-bottom: 4px; }}
  .results .detail-sub {{ color: var(--text-dim); font-size: 13px; margin-bottom: 20px; }}

  .btn {{
    padding: 10px 24px; border-radius: 8px; font-size: 14px;
    font-weight: 600; border: none; cursor: pointer; transition: all 0.15s;
  }}
  .btn-primary {{ background: var(--accent); color: var(--bg); }}
  .btn-primary:hover {{ background: var(--accent-hover); }}
  .btn-outline {{ background: transparent; border: 1px solid var(--border); color: var(--text); }}
  .btn-outline:hover {{ border-color: var(--accent); color: var(--accent); }}
  .action-row {{ display: flex; gap: 12px; justify-content: center; margin-top: 16px; }}

  .welcome {{ text-align: center; padding: 80px 20px; }}
  .welcome h2 {{ font-size: 28px; margin-bottom: 12px; }}
  .welcome p {{ color: var(--text-dim); font-size: 16px; max-width: 400px; margin: 0 auto; line-height: 1.6; }}

  @media (max-width: 768px) {{
    .sidebar {{ position: fixed; z-index: 100; transform: translateX(-100%); transition: transform 0.25s; }}
    .sidebar.open {{ transform: translateX(0); }}
    .main {{ margin-left: 0; padding: 20px; }}
    .menu-toggle {{
      display: block !important; position: fixed; top: 16px; left: 16px; z-index: 99;
      background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
      padding: 8px 12px; color: var(--text); font-size: 18px; cursor: pointer;
    }}
  }}
  .menu-toggle {{ display: none; }}
</style>
</head>
<body>
<button class="menu-toggle" onclick="document.querySelector('.sidebar').classList.toggle('open')">&#9776;</button>
<div class="app">
  <nav class="sidebar" id="sidebar">
    <h1>Heme Quiz</h1>
    <div class="tagline">INDE-223B Hematology</div>
    <div id="quiz-list"></div>
  </nav>
  <main class="main" id="main">
    <div class="welcome">
      <h2>Select a Quiz</h2>
      <p>Choose a lecture from the sidebar. Each lecture has a Pre-Quiz to test baseline knowledge and a Post-Quiz with clinical scenarios to test deeper understanding.</p>
    </div>
  </main>
</div>

<script>
const QUIZZES = {quiz_data_json};

let currentQuiz = null;
let answered = {{}};
let score = 0;
let revealed = {{}};

function init() {{
  const list = document.getElementById('quiz-list');
  let currentLectureNum = null;
  QUIZZES.forEach((q, i) => {{
    if (q.lecture_num !== currentLectureNum) {{
      currentLectureNum = q.lecture_num;
      if (i > 0) {{
        const divider = document.createElement('div');
        divider.className = 'lecture-divider';
        list.appendChild(divider);
      }}
      const header = document.createElement('div');
      header.className = 'lecture-header';
      header.textContent = q.lecture_title;
      list.appendChild(header);
    }}
    const btn = document.createElement('button');
    btn.className = 'quiz-btn';
    const isPre = q.quiz_type === 'pre';
    const badgeClass = isPre ? 'badge-pre' : 'badge-post';
    const badgeText = isPre ? 'PRE' : 'POST';
    btn.innerHTML = '<span class="badge ' + badgeClass + '">' + badgeText + '</span> ' +
      (isPre ? 'Pre-Quiz' : 'Post-Quiz') +
      '<span class="q-count">' + q.questions.length + ' Qs</span>';
    btn.onclick = () => loadQuiz(i);
    btn.id = 'qbtn-' + i;
    list.appendChild(btn);
  }});
}}

function loadQuiz(index) {{
  currentQuiz = index;
  answered = {{}};
  revealed = {{}};
  score = 0;
  const quiz = QUIZZES[index];

  document.querySelectorAll('.quiz-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('qbtn-' + index).classList.add('active');
  document.querySelector('.sidebar').classList.remove('open');

  const isPre = quiz.quiz_type === 'pre';
  const typeBadgeClass = isPre ? 'pre-badge' : 'post-badge';
  const typeBadgeText = isPre ? 'PRE-QUIZ' : 'POST-QUIZ';
  const main = document.getElementById('main');
  let html = '<div class="quiz-header">';
  html += '<div class="quiz-type-badge ' + typeBadgeClass + '">' + typeBadgeText + '</div>';
  html += '<h2>' + escHtml(quiz.lecture_title || quiz.title) + '</h2>';
  html += '<div class="meta">' + escHtml(quiz.subtitle) + '</div></div>';
  html += '<div class="progress-bar"><div class="progress-fill" id="progress" style="width:0%"></div></div>';
  html += '<div class="score-bar"><span id="score-text">0 of ' + quiz.questions.length + ' answered</span><span class="score" id="score-val"></span></div>';

  quiz.questions.forEach((q, qi) => {{
    html += '<div class="question-card" id="qcard-' + qi + '">';
    html += '<div class="q-number">Question ' + q.number + '</div>';
    html += '<div class="q-text">' + escHtml(q.question) + '</div>';
    html += '<div class="options" id="opts-' + qi + '">';
    ['A','B','C','D'].forEach(letter => {{
      if (q.options[letter]) {{
        html += '<div class="option-wrapper">';
        html += '<button class="option-btn" id="opt-' + qi + '-' + letter + '" onclick="selectAnswer(' + qi + ',\\'' + letter + '\\')">';
        html += '<span class="letter">' + letter + '</span>';
        html += '<span>' + escHtml(q.options[letter]) + '</span>';
        html += '</button>';
        // Per-option explanation (hidden initially)
        const optExp = q.option_explanations && q.option_explanations[letter];
        if (optExp) {{
          const isCorrectOpt = letter === q.correct;
          html += '<div class="opt-explanation ' + (isCorrectOpt ? 'opt-correct' : 'opt-wrong') + '" id="optexp-' + qi + '-' + letter + '">';
          html += escHtml(optExp.text);
          html += '</div>';
        }}
        html += '</div>';
      }}
    }});
    html += '</div>';
    // Reveal answer button
    html += '<button class="reveal-btn" id="reveal-' + qi + '" onclick="revealAnswer(' + qi + ')">';
    html += '<span class="icon">&#128161;</span> I Don\\'t Know &mdash; Show Me the Answer';
    html += '</button>';
    // Fallback general explanation
    html += '<div class="explanation" id="exp-' + qi + '"><div class="exp-label"></div><div class="exp-text"></div></div>';
    html += '</div>';
  }});

  html += '<div id="results-area"></div>';
  main.innerHTML = html;
  window.scrollTo(0, 0);
}}

function selectAnswer(qi, letter) {{
  if (answered[qi] || revealed[qi]) return;

  const quiz = QUIZZES[currentQuiz];
  const q = quiz.questions[qi];
  answered[qi] = letter;
  const isCorrect = letter === q.correct;
  if (isCorrect) score++;

  // Hide reveal button
  document.getElementById('reveal-' + qi).classList.add('hidden');

  // Style options and show per-option explanations
  ['A','B','C','D'].forEach(l => {{
    const btn = document.getElementById('opt-' + qi + '-' + l);
    if (!btn) return;
    btn.classList.add('disabled');
    if (l === q.correct) btn.classList.add('correct');
    if (l === letter && !isCorrect) btn.classList.add('wrong');
    if (l === letter) btn.classList.add('selected');

    // Show per-option explanation
    const optExp = document.getElementById('optexp-' + qi + '-' + l);
    if (optExp) optExp.classList.add('show');
  }});

  // Style card
  const card = document.getElementById('qcard-' + qi);
  card.classList.add(isCorrect ? 'answered-correct' : 'answered-wrong');

  // Show general explanation if no per-option explanations exist
  const hasOptExp = q.option_explanations && Object.keys(q.option_explanations).length > 0;
  if (!hasOptExp && q.explanation) {{
    const exp = document.getElementById('exp-' + qi);
    exp.classList.add('show', isCorrect ? 'correct-exp' : 'wrong-exp');
    exp.querySelector('.exp-label').textContent = isCorrect ? 'Correct!' : 'Incorrect - Answer: ' + q.correct;
    exp.querySelector('.exp-text').textContent = q.explanation;
  }}

  updateProgress(quiz);
}}

function revealAnswer(qi) {{
  if (answered[qi] || revealed[qi]) return;

  const quiz = QUIZZES[currentQuiz];
  const q = quiz.questions[qi];
  revealed[qi] = true;

  // Hide reveal button
  document.getElementById('reveal-' + qi).classList.add('hidden');

  // Style options
  ['A','B','C','D'].forEach(l => {{
    const btn = document.getElementById('opt-' + qi + '-' + l);
    if (!btn) return;
    btn.classList.add('disabled');
    if (l === q.correct) btn.classList.add('correct');

    // Show per-option explanation
    const optExp = document.getElementById('optexp-' + qi + '-' + l);
    if (optExp) optExp.classList.add('show');
  }});

  // Style card
  const card = document.getElementById('qcard-' + qi);
  card.classList.add('answered-reveal');

  // Show general explanation if no per-option explanations
  const hasOptExp = q.option_explanations && Object.keys(q.option_explanations).length > 0;
  if (!hasOptExp && q.explanation) {{
    const exp = document.getElementById('exp-' + qi);
    exp.classList.add('show', 'reveal-exp');
    exp.querySelector('.exp-label').textContent = 'Answer: ' + q.correct;
    exp.querySelector('.exp-text').textContent = q.explanation;
  }}

  updateProgress(quiz);
}}

function updateProgress(quiz) {{
  const total = quiz.questions.length;
  const answeredCount = Object.keys(answered).length;
  const revealedCount = Object.keys(revealed).length;
  const totalDone = answeredCount + revealedCount;
  document.getElementById('progress').style.width = (totalDone / total * 100) + '%';
  document.getElementById('score-text').textContent = totalDone + ' of ' + total + ' answered';
  const scoreText = score + '/' + answeredCount + ' correct';
  const revealText = revealedCount > 0 ? ' (' + revealedCount + ' revealed)' : '';
  document.getElementById('score-val').textContent = answeredCount > 0 ? scoreText + revealText : revealedCount > 0 ? revealedCount + ' revealed' : '';
  if (totalDone === total) showResults();
}}

function showResults() {{
  const quiz = QUIZZES[currentQuiz];
  const total = quiz.questions.length;
  const answeredCount = Object.keys(answered).length;
  const revealedCount = Object.keys(revealed).length;
  const pct = answeredCount > 0 ? Math.round(score / answeredCount * 100) : 0;
  let grade = 'needs-work';
  if (pct >= 80) grade = 'great';
  else if (pct >= 60) grade = 'ok';

  const area = document.getElementById('results-area');
  area.innerHTML = '<div class="results">' +
    '<h3>Quiz Complete!</h3>' +
    '<div class="pct ' + grade + '">' + pct + '%</div>' +
    '<div class="detail">' + score + ' correct out of ' + answeredCount + ' attempted</div>' +
    (revealedCount > 0 ? '<div class="detail-sub">' + revealedCount + ' question' + (revealedCount > 1 ? 's' : '') + ' revealed (not scored)</div>' : '') +
    '<div class="action-row">' +
    '<button class="btn btn-primary" onclick="loadQuiz(' + currentQuiz + ')">Retry Quiz</button>' +
    '<button class="btn btn-outline" onclick="reviewMissed()">Review Missed</button>' +
    '</div></div>';
}}

function reviewMissed() {{
  const quiz = QUIZZES[currentQuiz];
  let firstMissed = null;
  quiz.questions.forEach((q, qi) => {{
    const card = document.getElementById('qcard-' + qi);
    if (answered[qi] === q.correct) {{
      card.style.display = 'none';
    }} else {{
      card.style.display = 'block';
      if (!firstMissed) firstMissed = card;
    }}
  }});
  if (firstMissed) firstMissed.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  document.getElementById('results-area').innerHTML = '';
}}

function escHtml(s) {{
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

init();
</script>
</body>
</html>'''
    return html


def main():
    quiz_files = sorted(glob.glob(os.path.join(QUIZ_DIR, "[0-9][0-9]-*-pre.md")) +
                        glob.glob(os.path.join(QUIZ_DIR, "[0-9][0-9]-*-post.md")))
    print(f"Found {len(quiz_files)} quiz files")

    quizzes = []
    for f in sorted(quiz_files):
        basename = os.path.basename(f)
        lecture_num = basename[:2]
        quiz_type = 'pre' if '-pre.md' in basename else 'post'

        print(f"  Parsing {basename}...")
        quiz = parse_quiz_file(f)
        quiz['lecture_num'] = lecture_num
        quiz['quiz_type'] = quiz_type

        # Extract lecture title from quiz title (strip pre/post suffix)
        lecture_title = re.sub(r'\s*[—–-]+\s*(Pre|Post)[- ]Quiz\s*$', '', quiz['title']).strip()
        quiz['lecture_title'] = lecture_title

        q_with_opt_exp = sum(1 for q in quiz['questions'] if q.get('option_explanations'))
        print(f"    -> {len(quiz['questions'])} questions ({q_with_opt_exp} with per-option explanations)")
        if quiz['questions']:
            quizzes.append(quiz)

    # Sort by lecture number, then pre before post
    quizzes.sort(key=lambda q: (q['lecture_num'], 0 if q['quiz_type'] == 'pre' else 1))

    total_q = sum(len(q['questions']) for q in quizzes)
    total_opt = sum(1 for q in quizzes for qq in q['questions'] if qq.get('option_explanations'))
    print(f"\nTotal: {total_q} questions ({total_opt} with per-option explanations) across {len(quizzes)} quizzes")

    html = generate_html(quizzes)
    with open(OUTPUT_FILE, 'w') as f:
        f.write(html)
    print(f"\nQuiz app written to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
