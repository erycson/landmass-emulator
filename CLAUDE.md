# LandMass Emulator

Leia `docs/SAD.md` antes de qualquer mudança: arquitetura, restrições (R1–R6), protocolo e marcos.
Evidências de engenharia reversa ficam em `re/` (comece por `re/NOTES.md`).

- Atualize `docs/SAD.md` quando mudar arquitetura, protocolo ou decisão. Não escreva diário de desenvolvimento nele.
- Gates antes de commit: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest`.
- Nunca rode `git clean`.
