# Eval results

15 cases | precision 0.857 | recall 1.0 | avg latency 0.46ms | LLM calls: 0

| case | outcome | actual |
|---|---|---|
| flagship | useful_intervention | Ask Aaditya to review the Sarvam Kivi service. |
| possessive | useful_intervention | Send it to Aaditya's team. |
| product-capitalized | useful_intervention | Restart the Kivi backend. |
| fruit-lowercase | correct_abstention | I ate a kiwi for breakfast. |
| promoted-misspelling | useful_intervention | The Sarvam roadmap is ready. |
| already-correct | correct_abstention | Ask Aaditya about the Sarvam Kivi launch. |
| candidate-too-weak | correct_abstention | Open the Figna file. |
| ambiguous-cluster | correct_abstention | Ankith owns this task. |
| unknown-name | correct_abstention | Loop in Ramesh tomorrow. |
| common-word-plain | correct_abstention | The notion of fairness matters. |
| common-word-capitalized | correct_abstention | Update the Notion doc. |
| promoted-already-correct | correct_abstention | Priya approved the design. |
| promoted-variant | useful_intervention | Priya signed off. |
| lowercase-name | useful_intervention | Tell Aaditya it works. |
| sentence-start-fruit | incorrect_intervention | Kivi is my favorite fruit. |

## Outcome counts

- useful_intervention: 6
- correct_abstention: 8
- incorrect_intervention: 1
- missed_correction: 0
