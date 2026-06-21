.PHONY: all install clean

BINARY=webui.py
DATA_DIR=/usr/local/webui

all:
	@echo "Nessuna compilazione necessaria — Python non va compilato."
	@echo "Usa: make install  (copia i file nella posizione giusta)"

install:
	install -d $(DATA_DIR)/apps
	install -m 755 backend/$(BINARY) /usr/local/bin/$(BINARY)
	install -m 644 backend/$(BINARY) $(DATA_DIR)/
	cp -r backend/webui $(DATA_DIR)/webui
	install -m 644 opencasa.json.example /etc/opencasa.json
	cp -r frontend/dist/* $(DATA_DIR)/ 2>/dev/null || cp -r frontend/* $(DATA_DIR)/ 2>/dev/null || true
	install -m 755 scripts/webui /etc/rc.d/webui
	@echo ""
	@echo "Installato su $(DATA_DIR)."
	@echo "Per abilitare e avviare:"
	@echo "  rcctl enable webui"
	@echo "  rcctl start webui"
	@echo ""
	@echo "Prima di avviare, modificare /etc/opencasa.json:"
	@echo "  openssl rand -hex 32  # generare jwt_secret"

clean:
	rm -rf __pycache__ */__pycache__ 2>/dev/null; true
