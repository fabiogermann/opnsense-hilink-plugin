# HiLink OPNsense Plugin Makefile
# Build, test, and package the HiLink plugin

# Variables
PLUGIN_NAME := os-hilink
VERSION := $(shell git describe --tags --always 2>/dev/null || echo "1.0.0")
BUILD_DIR := build
DIST_DIR := dist
SRC_DIR := src
TEST_DIR := tests
PYTHON := python3
PIP := pip3

# OPNsense paths
OPNSENSE_ROOT := /usr/local
OPNSENSE_ETC := $(OPNSENSE_ROOT)/etc
OPNSENSE_WWW := $(OPNSENSE_ROOT)/www
OPNSENSE_SCRIPTS := $(OPNSENSE_ROOT)/opnsense

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# Default target
.PHONY: all
all: clean build test package
	@echo "$(GREEN)✓ Build complete$(NC)"

# Help target
.PHONY: help
help:
	@echo "HiLink OPNsense Plugin Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  all          - Clean, build, test, and package"
	@echo "  build        - Build the plugin"
	@echo "  test         - Run tests"
	@echo "  package      - Create distribution package"
	@echo "  install      - Install to local OPNsense"
	@echo "  uninstall    - Remove from local OPNsense"
	@echo "  clean        - Clean build artifacts"
	@echo "  dev-setup    - Set up development environment"
	@echo "  lint         - Run code linters"
	@echo "  format       - Format code with black"
	@echo "  docs         - Generate documentation"
	@echo "  version      - Show version"

# Version target
.PHONY: version
version:
	@echo "$(PLUGIN_NAME) version: $(VERSION)"

# Development setup
.PHONY: dev-setup
dev-setup:
	@echo "$(YELLOW)Setting up development environment...$(NC)"
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Development environment ready$(NC)"

# Build target
.PHONY: build
build:
	@echo "$(YELLOW)Building $(PLUGIN_NAME)...$(NC)"
	@mkdir -p $(BUILD_DIR)
	
	# Compile Python files
	@echo "Compiling Python modules..."
	@find $(SRC_DIR) -name "*.py" -exec $(PYTHON) -m py_compile {} \;
	
	# Copy source files to build directory
	@echo "Copying source files..."
	@cp -r $(SRC_DIR)/* $(BUILD_DIR)/
	
	# Remove Python cache files
	@find $(BUILD_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(BUILD_DIR) -name "*.pyc" -delete 2>/dev/null || true
	
	@echo "$(GREEN)✓ Build complete$(NC)"

# Test target
.PHONY: test
test:
	@echo "$(YELLOW)Running tests...$(NC)"
	@if [ -d "$(TEST_DIR)" ]; then \
		$(PYTHON) -m pytest $(TEST_DIR) -v --cov=src/opnsense/scripts/hilink --cov-report=term-missing; \
	else \
		echo "$(YELLOW)⚠ No tests directory found$(NC)"; \
	fi

# Lint target
.PHONY: lint
lint:
	@echo "$(YELLOW)Running linters...$(NC)"
	@echo "Running pylint..."
	@find $(SRC_DIR) -name "*.py" -exec pylint {} \; || true
	@echo "Running mypy..."
	@mypy $(SRC_DIR)/opnsense/scripts/hilink --ignore-missing-imports || true
	@echo "$(GREEN)✓ Linting complete$(NC)"

# Format target
.PHONY: format
format:
	@echo "$(YELLOW)Formatting code...$(NC)"
	@black $(SRC_DIR)/opnsense/scripts/hilink
	@echo "$(GREEN)✓ Formatting complete$(NC)"

# Package target
.PHONY: package
package: build
	@echo "$(YELLOW)Creating package...$(NC)"
	@mkdir -p $(DIST_DIR)
	
	# Create package structure
	@mkdir -p $(DIST_DIR)/$(PLUGIN_NAME)-$(VERSION)
	@cp -r $(BUILD_DIR)/* $(DIST_DIR)/$(PLUGIN_NAME)-$(VERSION)/
	@cp -r pkg $(DIST_DIR)/$(PLUGIN_NAME)-$(VERSION)/
	
	# Create tarball
	@cd $(DIST_DIR) && \
		tar -czf $(PLUGIN_NAME)-$(VERSION).txz \
		--exclude='*.pyc' \
		--exclude='__pycache__' \
		$(PLUGIN_NAME)-$(VERSION)
	
	# Clean up temporary directory
	@rm -rf $(DIST_DIR)/$(PLUGIN_NAME)-$(VERSION)
	
	@echo "$(GREEN)✓ Package created: $(DIST_DIR)/$(PLUGIN_NAME)-$(VERSION).txz$(NC)"

# Install target (requires root)
.PHONY: install
install: build
	@echo "$(YELLOW)Installing to OPNsense...$(NC)"
	@if [ "$$(id -u)" != "0" ]; then \
		echo "$(RED)✗ This target must be run as root$(NC)"; \
		exit 1; \
	fi
	
	# Stop service if running
	@service hilink stop 2>/dev/null || true
	
	# Install Python scripts
	@echo "Installing Python scripts..."
	@mkdir -p $(OPNSENSE_SCRIPTS)/scripts/hilink
	@cp -r $(BUILD_DIR)/opnsense/scripts/hilink/* $(OPNSENSE_SCRIPTS)/scripts/hilink/
	@chmod +x $(OPNSENSE_SCRIPTS)/scripts/hilink/hilink_service.py
	
	# Install MVC components
	@echo "Installing MVC components..."
	@if [ -d "$(BUILD_DIR)/opnsense/mvc" ]; then \
		cp -r $(BUILD_DIR)/opnsense/mvc/* $(OPNSENSE_ROOT)/opnsense/mvc/; \
	fi
	
	# Install service configuration
	@echo "Installing service configuration..."
	@if [ -d "$(BUILD_DIR)/opnsense/service" ]; then \
		cp -r $(BUILD_DIR)/opnsense/service/* $(OPNSENSE_ROOT)/opnsense/service/; \
	fi
	
	# Install web components
	@echo "Installing web components..."
	@if [ -d "$(BUILD_DIR)/opnsense/www" ]; then \
		cp -r $(BUILD_DIR)/opnsense/www/* $(OPNSENSE_WWW)/; \
	fi
	
	# Create required directories
	@mkdir -p /var/log/hilink
	@mkdir -p /var/db/hilink/rrd
	@mkdir -p /usr/local/etc/hilink
	
	# Restart configd
	@service configd restart
	
	@echo "$(GREEN)✓ Installation complete$(NC)"
	@echo "$(YELLOW)Please navigate to Services > HiLink in the OPNsense web interface$(NC)"

# Uninstall target (requires root)
.PHONY: uninstall
uninstall:
	@echo "$(YELLOW)Uninstalling from OPNsense...$(NC)"
	@if [ "$$(id -u)" != "0" ]; then \
		echo "$(RED)✗ This target must be run as root$(NC)"; \
		exit 1; \
	fi
	
	# Stop service
	@service hilink stop 2>/dev/null || true
	
	# Remove files
	@echo "Removing files..."
	@rm -rf $(OPNSENSE_SCRIPTS)/scripts/hilink
	@rm -rf $(OPNSENSE_ROOT)/opnsense/mvc/app/controllers/OPNsense/HiLink
	@rm -rf $(OPNSENSE_ROOT)/opnsense/mvc/app/models/OPNsense/HiLink
	@rm -rf $(OPNSENSE_ROOT)/opnsense/mvc/app/views/OPNsense/HiLink
	@rm -rf $(OPNSENSE_WWW)/js/hilink
	@rm -f $(OPNSENSE_ROOT)/opnsense/service/conf/actions.d/actions_hilink.conf
	
	# Remove data (with confirmation)
	@echo "$(YELLOW)Remove data files? (y/N)$(NC)"
	@read -r response; \
	if [ "$$response" = "y" ] || [ "$$response" = "Y" ]; then \
		rm -rf /var/log/hilink; \
		rm -rf /var/db/hilink; \
		rm -rf /usr/local/etc/hilink; \
		echo "$(GREEN)✓ Data files removed$(NC)"; \
	else \
		echo "Data files preserved"; \
	fi
	
	# Restart configd
	@service configd restart
	
	@echo "$(GREEN)✓ Uninstallation complete$(NC)"

# Clean target
.PHONY: clean
clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@rm -rf $(BUILD_DIR)
	@rm -rf $(DIST_DIR)
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete$(NC)"

# Documentation target
.PHONY: docs
docs:
	@echo "$(YELLOW)Generating documentation...$(NC)"
	@if [ -d "docs" ]; then \
		$(PYTHON) -m pydoc -w $(SRC_DIR)/opnsense/scripts/hilink/*.py; \
		mv *.html docs/; \
		echo "$(GREEN)✓ Documentation generated in docs/$(NC)"; \
	else \
		echo "$(RED)✗ docs directory not found$(NC)"; \
	fi

# Development server target
.PHONY: dev-server
dev-server:
	@echo "$(YELLOW)Starting development server...$(NC)"
	@$(PYTHON) $(SRC_DIR)/opnsense/scripts/hilink/hilink_service.py \
		--foreground \
		--debug \
		--config ./dev-config

# Check dependencies
.PHONY: check-deps
check-deps:
	@echo "$(YELLOW)Checking dependencies...$(NC)"
	@$(PYTHON) -c "import aiohttp" 2>/dev/null || echo "$(RED)✗ aiohttp not installed$(NC)"
	@$(PYTHON) -c "import xmltodict" 2>/dev/null || echo "$(RED)✗ xmltodict not installed$(NC)"
	@$(PYTHON) -c "import bs4" 2>/dev/null || echo "$(RED)✗ beautifulsoup4 not installed$(NC)"
	@$(PYTHON) -c "import daemon" 2>/dev/null || echo "$(RED)✗ python-daemon not installed$(NC)"
	@$(PYTHON) -c "import rrdtool" 2>/dev/null || echo "$(RED)✗ rrdtool not installed$(NC)"
	@echo "$(GREEN)✓ Dependency check complete$(NC)"

# Create release
.PHONY: release
release: clean test package
	@echo "$(YELLOW)Creating release $(VERSION)...$(NC)"
	@mkdir -p releases
	@cp $(DIST_DIR)/$(PLUGIN_NAME)-$(VERSION).txz releases/
	@cd releases && sha256sum $(PLUGIN_NAME)-$(VERSION).txz > $(PLUGIN_NAME)-$(VERSION).txz.sha256
	@echo "$(GREEN)✓ Release created in releases/$(NC)"

# Install Python dependencies
.PHONY: deps
deps:
	@echo "$(YELLOW)Installing Python dependencies...$(NC)"
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

# Run specific test file
.PHONY: test-file
test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)✗ Please specify FILE=path/to/test.py$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Running test: $(FILE)$(NC)"
	@$(PYTHON) -m pytest $(FILE) -v

# Watch for changes and run tests
.PHONY: watch
watch:
	@echo "$(YELLOW)Watching for changes...$(NC)"
	@while true; do \
		find $(SRC_DIR) $(TEST_DIR) -name "*.py" | entr -c make test; \
	done

# Validate configuration
.PHONY: validate
validate:
	@echo "$(YELLOW)Validating configuration...$(NC)"
	@$(PYTHON) -c "from src.opnsense.scripts.hilink.lib.config_manager import ConfigManager; \
		cm = ConfigManager(); \
		cm.load(); \
		errors = cm.validate(); \
		if errors: print('Errors:', errors); exit(1); \
		else: print('✓ Configuration valid')"

# Show statistics
.PHONY: stats
stats:
	@echo "$(YELLOW)Project statistics:$(NC)"
	@echo "Lines of Python code:"
	@find $(SRC_DIR) -name "*.py" -exec wc -l {} + | tail -1
	@echo "Number of Python files:"
	@find $(SRC_DIR) -name "*.py" | wc -l
	@echo "Number of test files:"
	@find $(TEST_DIR) -name "test_*.py" 2>/dev/null | wc -l || echo "0"

.PHONY: check-syntax
check-syntax:
	@echo "$(YELLOW)Checking Python syntax...$(NC)"
	@find $(SRC_DIR) -name "*.py" -exec $(PYTHON) -m py_compile {} \;
	@echo "$(GREEN)✓ Syntax check passed$(NC)"