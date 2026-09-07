# Eval results

59 cases | precision 1.0 | recall 0.97 | avg latency 0.74ms | LLM calls: 0

| case | outcome | actual |
|---|---|---|
| promoted-priya | useful_intervention | Forward this thread to Priya. |
| promoted-meera | useful_intervention | Forward this thread to Meera. |
| promoted-nikhil | useful_intervention | Forward this thread to Nikhil. |
| promoted-ananya | useful_intervention | Forward this thread to Ananya. |
| promoted-sana | useful_intervention | Forward this thread to Sana. |
| promoted-arjun | useful_intervention | Forward this thread to Arjun. |
| promoted-yash | useful_intervention | Forward this thread to Yash. |
| promoted-aarav | useful_intervention | Forward this thread to Aarav. |
| promoted-kavya | useful_intervention | Forward this thread to Kavya. |
| promoted-riya | useful_intervention | Forward this thread to Riya. |
| already-correct-priya | correct_abstention | Tell Priya the deck is ready for review. |
| already-correct-meera | correct_abstention | Tell Meera the deck is ready for review. |
| already-correct-nikhil | correct_abstention | Tell Nikhil the deck is ready for review. |
| already-correct-ananya | correct_abstention | Tell Ananya the deck is ready for review. |
| corrected-aaditya | useful_intervention | Remind me to email Aaditya tomorrow. |
| corrected-ishaan | useful_intervention | Remind me to email Ishaan tomorrow. |
| corrected-vihaan | useful_intervention | Remind me to email Vihaan tomorrow. |
| corrected-simran | useful_intervention | Remind me to email Simran tomorrow. |
| corrected-rohan | useful_intervention | Remind me to email Rohan tomorrow. |
| corrected-diya | useful_intervention | Remind me to email Diya tomorrow. |
| corrected-name-sentence-start-tradeoff | missed_correction | Rohaan mentioned the deadline moved to Friday. |
| ambiguous-ankith | correct_abstention | Send the invoice to Ankith please. |
| ambiguous-kabir | correct_abstention | Send the invoice to Kabir please. |
| candidate-tanvi | correct_abstention | Tanavi is joining the standup at ten. |
| candidate-devansh | correct_abstention | Devanash is joining the standup at ten. |
| collision-kiwi-product | useful_intervention | Can we move this conversation to Kivi? |
| collision-kiwi-literal | correct_abstention | I ate a kiwi for breakfast. |
| collision-kiwi-sentence-start | correct_abstention | Kiwi is my favorite fruit. |
| collision-lift-product | useful_intervention | Can we move this conversation to Lyft? |
| collision-lift-literal | correct_abstention | Please lift the box carefully. |
| collision-lift-sentence-start | correct_abstention | Lift with your legs, not your back. |
| collision-zoom-product | useful_intervention | Can we move this conversation to Xoom? |
| collision-zoom-literal | correct_abstention | The car began to zoom down the highway. |
| collision-zoom-sentence-start | correct_abstention | Zoom lenses are heavier than primes. |
| collision-zero-product | useful_intervention | Can we move this conversation to Xero? |
| collision-zero-literal | correct_abstention | The counter reset back to zero. |
| collision-zero-sentence-start | correct_abstention | Zero tolerance policies rarely work. |
| collision-fire-product | useful_intervention | Can we move this conversation to Fyre? |
| collision-fire-literal | correct_abstention | Please put out the fire before we leave. |
| collision-fire-sentence-start | correct_abstention | Fire drills happen every month here. |
| collision-flicker-product | useful_intervention | Can we move this conversation to Flickr? |
| collision-flicker-literal | correct_abstention | The candle started to flicker in the wind. |
| collision-flicker-sentence-start | correct_abstention | Flicker is a common symptom of a loose bulb. |
| nearmiss-fiverr | useful_intervention | Restart the Fiverr service. |
| nearmiss-scribd | useful_intervention | Restart the Scribd service. |
| plain-sarvam | useful_intervention | File a bug against Sarvam. |
| plain-figma | useful_intervention | File a bug against Figma. |
| plain-coda | useful_intervention | File a bug against Coda. |
| plain-asana | useful_intervention | File a bug against Asana. |
| plain-canva | useful_intervention | File a bug against Canva. |
| candidate-loom | correct_abstention | The Looum integration needs testing. |
| unknown-name | correct_abstention | Loop in Ramesh tomorrow. |
| common-word-plain | correct_abstention | The notion of fairness matters. |
| common-word-capitalized-no-memory | correct_abstention | Update the Notion doc. |
| possessive-fresh | correct_abstention | Send it to Ishaan's team. |
| possessive-misspelled | useful_intervention | Send it to Ishaan's team. |
| multi-token-name-and-product | useful_intervention | Ask Priya to check the Fiverr outage. |
| lowercase-name-uncapitalized | useful_intervention | Tell Ishaan it works. |
| exact-match-no-decision | correct_abstention | Priya approved the design. |

## Outcome counts

- useful_intervention: 32
- correct_abstention: 26
- incorrect_intervention: 0
- missed_correction: 1
