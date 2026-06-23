# Prompts

All prompts are versioned text files in `backend/open_webui/memory_layer/prompts/`.

| Prompt | File | Purpose |
|--------|------|---------|
| Memory extractor | `memory_extractor_v1.txt` | Extract atomic memories from a chat exchange |
| Anti-sycophancy | `anti_sycophancy_v1.txt` | Instruct LLM to avoid validation-by-default |
| Profile generator | `profile_generator_v1.txt` | Full profile regen from top-200 memories |
| Profile patcher | `profile_patcher_v1.txt` | Incremental patches from last 5 memories |
| Consolidation | `consolidation_v1.txt` | Synthesis memory from a cluster |
| Opening prompt | `opening_prompt_v1.txt` | Personalized greeting after inactivity |
| Document summarizer | `document_summarizer_v1.txt` | Summary of uploaded documents |

## Design Choices

- All prompts use **3rd person** ("L'utilisateur...") to avoid confusion with the LLM's own identity.
- Sensitivity flag is explicitly instructed in the extractor prompt with concrete examples (deuil, santé mentale).
- Anti-sycophancy is a long, prescriptive block rather than a short instruction, because short instructions are often ignored by chat-tuned models.
- Opening prompt generator receives the executive summary + top-10 memories to produce contextual questions without being too specific (avoiding creepiness).
