.PHONY: skills
skills:
	python -m app.prompts.export_skills

.PHONY: skills-check
skills-check:
	python -m app.prompts.export_skills --check

.PHONY: skills-clean
skills-clean:
	python -m app.prompts.export_skills --clean
