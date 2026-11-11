---
name: explain-and-quiz
description: Use at the end of each phase to explain what was built and quiz the owner for interview prep.
---

# Explain and quiz

1. Explain what the phase built and **why** each design choice was made, with the trade-offs and the alternatives rejected. Point to specific files and lines.
2. Ask **5 interview-style questions** about it, one at a time. Wait for the owner's answer before the next. Do not reveal answers first.
3. After each answer, say what was right, what was missing or wrong, and give a short model answer.
4. Append weak spots to `notes/interview-gaps.md` (create it if missing): date, phase, question, what was missing.
5. Finish by suggesting a commit message for the phase.

Likely themes: gRPC streaming vs unary, why write-behind, clock skew and last-write-wins, Redis failure, scaling to 10M viewers, hot keys, schema evolution with protobuf.
