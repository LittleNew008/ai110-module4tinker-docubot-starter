# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> _Your answer here._

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> _Your answer here._

**What outputs does DocuBot produce?**

> _Your answer here._

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

> _Your answer here._

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> _Your answer here._

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode:
- Retrieval only mode:
- RAG mode:

> _Your answer here._

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> _Your answer here._

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Unhelpful: says it has no information and asks for the codebase | Helpful: `Token Generation` section is first, but two unrelated AUTH.md sections follow | Helpful: names `generate_access_token` in `auth_utils.py`, cites AUTH.md | Only the retrieval and RAG modes can see the docs |
| How do I connect to the database? | Harmful: invents `DB_HOST`, `DB_PORT`, `DB_USER` and a generic ORM/connection string | Partly helpful: right topic, but the `Connection Configuration` section (which names `DATABASE_URL`) is not in the top 3 | Partly helpful: mentions `db.py`, SQLite and PostgreSQL, but never says `DATABASE_URL` | See failure case 2 |
| Which endpoint lists all users? | Unhelpful: asks which API is meant | Helpful but noisy: the DATABASE.md `projects` table is ranked first, `GET /api/users` second | Helpful: `GET /api/users`, cites API_REFERENCE.md | |
| How does a client refresh an access token? | Not tested: the API returned a 503 for this query | Helpful: `Client Workflow` section is first and includes `/api/refresh` | Helpful: call `/api/refresh`, cites AUTH.md | The 503 was a Gemini service error, not a finding |
| Is there any mention of payment processing in these docs? | Unhelpful: asks me to paste the docs | Helpful: "I do not know based on these docs." | Helpful: same refusal, and the LLM is never called | The docs really do not cover payments |
| Which fields are stored in the users table? | Harmful: confidently lists six fields (`id`, `username`, `email`, `password_hash`, `created_at`, `updated_at`); only `email` and `password_hash` are in the docs | Harmful: shows the `projects` table and `GET /api/users`, not the `users` table | Unhelpful: wrongly says "I do not know" | See failure case 1 |
| How long is an access token valid? | Weakly grounded: says "typically 1 hour (3600 seconds)", which matches only by luck and is framed as a general convention | Helpful but hard to read: the answer (3600 s default) is the last line of the third snippet | Helpful: `TOKEN_LIFETIME_SECONDS`, defaults to 3600 seconds, cites AUTH.md | Best example of RAG vs the other two |
| What hashing algorithm is used for password_hash? | Harmful: answers about PHP's `password_hash()` and bcrypt | Helpful: refuses | Helpful: refuses | The docs list a `password_hash` column but never name the algorithm |

Setup notes: mode 1 is `naive_answer_over_full_docs`. In the starter code it ignores the docs text and sends only the question to the model, so it never has the docs to ground on. Modes 2 and 3 run the same `retrieve` (heading sections, stop words dropped, `MIN_SCORE = 2`, top 3).

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
  When the question sounds like a generic technical one. For "Which fields are stored in the users table?" it opens with "Based on the current database schema" and lists a plausible schema (`id`, `username`, `created_at`, `updated_at`) that does not match DATABASE.md (`user_id`, `email`, `password_hash`, `joined_at`). The same happened for the required environment variables (`AUTH_SECRET`, `NEXTAUTH_SECRET`, Google and GitHub OAuth keys) and for the password hash algorithm (PHP bcrypt). Nothing in these answers marks them as guesses.
- When is retrieval only clearly better?  
  For refusals and for exact wording. It said "I do not know" on the payment and hashing questions without any LLM, and it shows the docs' own text, so nothing can be paraphrased wrongly. It is hard to read when the answer is a small part of a snippet: for the token lifetime, the reader has to scan three sections to find "3600 seconds" at the end of the third. For the `/api/projects/<project_id>` question, two of the three snippets are about other things.
- When is RAG clearly better than both?  
  When the answer is in the retrieved text but buried in it. For the token lifetime question RAG gave one sentence, the right variable and default, and the file it came from. That is the evidence of retrieval with the readability of the LLM. It is only as good as retrieval, though: when the right section is missing from the top 3, RAG either refuses or answers incompletely (see section 5).

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

> **Failure case 1: RAG refuses a question the docs answer.**
> Question: "Which fields are stored in the users table?"
> What happened: RAG replied "I do not know based on the docs I have." DATABASE.md has a `### users` section listing `user_id`, `email`, `password_hash` and `joined_at`. That section scored 1 against the query, below `MIN_SCORE = 2`, so `retrieve` dropped it. The top 3 were the `projects` table and `GET /api/users`, which do not contain the answer, so Gemini correctly refused on what it was given.
> What should have happened: return the `users` table section and answer with the four columns. The refusal logic worked as designed, but the evidence threshold is too strict for a section that has only one matching topic word.

> **Failure case 2: RAG gives an incomplete answer without saying so.**
> Question: "How do I connect to the database?"
> What happened: RAG described `db.py`, SQLite and PostgreSQL, citing DATABASE.md and SETUP.md. It never mentioned the `DATABASE_URL` environment variable, which is how the connection is configured. The `Connection Configuration` section scored 2, but three other sections scored as high or higher and `top_k = 3` cut it off. The query says "connect" and the section says "connection"; there is no stemming, so those do not match.
> What should have happened: the answer should lead with `DATABASE_URL` and its SQLite and PostgreSQL examples. A reader would trust this answer because it cites files, but it leaves out the most important step.

**When should DocuBot say “I do not know based on the docs I have”?**  
Give at least two specific situations.

> - The docs do not mention the topic at all, for example "Is there any mention of payment processing in these docs?" or "What is the capital of France?". Here `retrieve` finds nothing above `MIN_SCORE`, and both modes refuse without calling the LLM.
> - The docs mention the subject but not the detail asked for, for example "What hashing algorithm is used for password_hash?". DATABASE.md lists a `password_hash` column but never names an algorithm. Both modes refused this one.
> - The retrieved snippets are related but do not contain the answer. In RAG mode the prompt tells Gemini to reply with the refusal sentence in this case. Mode 1 (naive) has no way to refuse reliably: it sometimes asks for more context, and sometimes invents an answer.

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

> _Your answer here._

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. _Limitation 1_
2. _Limitation 2_
3. _Limitation 3_

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. _Improvement 1_
2. _Improvement 2_
3. _Improvement 3_

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

> _Your answer here._

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- _Guideline 1_
- _Guideline 2_
- _Guideline 3 (optional)_

---
