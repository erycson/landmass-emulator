# LandMass Emulator

Leia `docs/README.md` (índice do SAD) antes de qualquer mudança: arquitetura, restrições (R1–R6), protocolo e marcos.
Evidências de engenharia reversa ficam em `re/` (comece por `re/NOTES.md`).

- Atualize o arquivo de `docs/` do assunto afetado e o índice `docs/README.md`. Não escreva diário de desenvolvimento.
- Gates antes de commit: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest`.
- Nunca rode `git clean`.
