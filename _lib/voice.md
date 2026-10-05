# Voice rules for sheets

Sheets use simple English. About 80% of ASD-STE100 is the goal. The build checks some rules.
You check the rest.

## What the build checks

- `voice-words.json` lists words to replace and words to ban. A stem matches the word and its endings.
- Every `label`, `instruction`, and `prose` field has a cap:
  - `label`: 12 words, 1 sentence.
  - `instruction`: 20 words per sentence, 2 sentences.
  - `prose`: 25 words per sentence. The field sets the sentence count.
- No em dash. Split the sentence.
- Code spans are not checked. Write them as `x` or `<code>x</code>`.
- `literal` fields are not checked.

## What you check yourself

- One meaning per word. Pick one word for one thing and keep it.
- Use active voice. Write "The worker retries", not "Retries are performed".
- Use noun clusters of 3 words at most. Write "retry delay", not "outbox worker retry delay policy".
- One instruction per sentence.
- Give numbers and names exactly.
- Cut hedging words that change nothing, such as "basically" and "simply".
- Use short common words: "use", "start", "stop", "help".
