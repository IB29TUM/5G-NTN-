# OAI-NTN-ZeroRF
# Targets: check, run, stop, gui, pull, clean, logs

.PHONY: check run stop gui pull clean logs

SCRIPT_DIR := scripts
GUI_DIR := gui

check:
	$(SCRIPT_DIR)/check_env.sh

run:
	$(SCRIPT_DIR)/run_demo.sh

stop:
	$(SCRIPT_DIR)/teardown.sh

gui:
	cd $(GUI_DIR) && python3 -c "import flask" 2>/dev/null || pip install -r requirements.txt
	@fuser -k 5001/tcp 2>/dev/null || true
	@sleep 1
	@echo "Open http://localhost:5001 in your browser"
	cd $(GUI_DIR) && python3 app.py

pull:
	docker pull mysql:8.0
	docker pull oaisoftwarealliance/oai-amf:v2.1.10
	docker pull oaisoftwarealliance/oai-smf:v2.1.10
	docker pull oaisoftwarealliance/oai-upf:v2.1.10
	docker pull oaisoftwarealliance/oai-gnb:2026.w09
	docker pull oaisoftwarealliance/oai-nr-ue:2026.w09
	docker pull oaisoftwarealliance/trf-gen-cn5g:focal

clean:
	docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
	rm -f logs/*.log reports/summary.json reports/kpis.md reports/callflow.md

logs:
	docker compose logs -f 2>/dev/null || docker-compose logs -f
