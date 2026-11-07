#!/bin/bash
# ============================================
#   Lauda Code - Auto Installer & Launcher
#   Developed by: ERROR
#   TG: https://t.me/aab_ho_ga_comeback
#   GitHub: ERROR0101r
# ============================================

# ---------- Colors ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'
NC='\033[0m'; BOLD='\033[1m'

# ---------- Config ----------
INSTALL_DIR="$HOME/.lauda-code"
BIN_DIR="$HOME/.local/bin"
LAUDA_PY="$INSTALL_DIR/lauda_code.py"
VERSION_FILE="$INSTALL_DIR/.version"
REPO_URL="https://github.com/ERROR0101r/lauda-code.git"
VERSION_JSON_URL="https://raw.githubusercontent.com/ERROR0101r/lauda-code/main/version.json"
DESKTOP_DIR="$HOME/Desktop"
APPS_DIR="$HOME/.local/share/applications"

# ---------- Helpers ----------
log()   { echo -e "${BLUE}◈${NC} $1"; }
ok()    { echo -e "${GREEN}✔${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "${RED}✘${NC} $1"; }
header(){ echo -e "\n${MAGENTA}${BOLD}◈ ─── $1 ─── ◈${NC}\n"; }
has()   { command -v "$1" >/dev/null 2>&1; }

# ---------- Interactive TTY helpers ----------
have_tty() { { : </dev/tty; } 2>/dev/null; }

sanitize() {
    local s="$1"
    s="${s//$'\r'/}"; s="${s//$'\n'/}"; s="${s//$'\t'/}"
    s="${s// /}";     s="${s//$'\0'/}"
    printf '%s' "$s"
}

read_tty() {
    local __var="$1" __prompt="$2" __line=""
    if ! IFS= read -rp "$__prompt" __line </dev/tty; then return 1; fi
    __line=$(sanitize "$__line")
    printf -v "$__var" '%s' "$__line"
    return 0
}

pause() {
    echo
    read_tty _ "↳ Press Enter to return to menu..." || true
}

detect_pkg_manager() {
    if has apt-get; then echo apt
    elif has dnf;    then echo dnf
    elif has yum;    then echo yum
    elif has pacman; then echo pacman
    elif has apk;    then echo apk
    elif has brew;   then echo brew
    elif has pkg;    then echo pkg
    else echo unknown; fi
}

# ---------- Dependencies ----------
check_dependencies() {
    header "Checking Dependencies"
    local PKG_MGR=$(detect_pkg_manager)
    log "Package manager: $PKG_MGR"

    local sys_deps=("git|git" "python3|python3" "pip3|python3-pip" "curl|curl")
    local missing=()

    for e in "${sys_deps[@]}"; do
        local c="${e%%|*}"; local p="${e##*|}"
        if has "$c"; then ok "$c found"; else warn "$c missing"; missing+=("$c|$p"); fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        local a=""
        read_tty a "↳ Install missing system packages now? [Y/n]: " || a=""
        a=${a:-Y}
        if [[ "$a" =~ ^[Yy]$ ]]; then
            for e in "${missing[@]}"; do
                local c="${e%%|*}"; local p="${e##*|}"
                log "Installing $c..."
                case "$PKG_MGR" in
                    apt)    sudo apt-get update -y && sudo apt-get install -y "$p" ;;
                    dnf)    sudo dnf install -y "$p" ;;
                    yum)    sudo yum install -y "$p" ;;
                    pacman) sudo pacman -Sy --noconfirm "$p" ;;
                    apk)    sudo apk add "$p" ;;
                    brew)   brew install "$p" ;;
                    pkg)    pkg install -y "$p" ;;
                    *)      fail "Unsupported package manager. Install $c manually." ;;
                esac
            done
        fi
    else
        ok "System dependencies OK."
    fi

    log "Checking Python packages..."
    python3 -m pip install --quiet --upgrade pip 2>/dev/null || true

    for pkg in requests rich; do
        if python3 -c "import $pkg" 2>/dev/null; then
            ok "python: $pkg installed"
        else
            warn "python: $pkg missing — installing..."
            python3 -m pip install --quiet --user "$pkg" \
                || python3 -m pip install --quiet --break-system-packages "$pkg" \
                || fail "Could not install $pkg"
        fi
    done
    ok "Dependency check complete."
}

# ---------- Clone Repo ----------
clone_repo() {
    header "Cloning Repository"
    if [ -d "$INSTALL_DIR/.git" ]; then
        ok "Repository already exists."
        return 0
    fi
    if [ -d "$INSTALL_DIR" ]; then
        warn "Directory exists but is not a git repo. Removing..."
        rm -rf "$INSTALL_DIR"
    fi
    log "Cloning from GitHub..."
    if git clone "$REPO_URL" "$INSTALL_DIR" 2>/dev/null; then
        ok "Repository cloned successfully."
    else
        fail "Failed to clone repository. Check your internet or Git."
        exit 1
    fi
}

# ---------- Get Current Version ----------
get_local_version() {
    if [ -f "$VERSION_FILE" ]; then cat "$VERSION_FILE"
    elif [ -f "$INSTALL_DIR/version.json" ]; then
        grep -oE '"version"[[:space:]]*:[[:space:]]*"[^"]+"' "$INSTALL_DIR/version.json" | head -n1 | sed -E 's/.*"([^"]+)"$/\1/'
    else echo "0.0.0"; fi
}

# ---------- Clean Unwanted Files ----------
clean_unwanted() {
    header "Cleaning Unwanted Files"
    local cleaned=0
    local patterns=(
        "version.json" "README.md" "readme.md" "Readme.md"
        "LICENSE" "LICENSE.md" "License" "license" "license.md"
        "CHANGELOG.md" "changelog.md" "CONTRIBUTING.md" "contributing.md"
        "CODE_OF_CONDUCT.md" ".gitignore" ".gitattributes" ".editorconfig"
        "*.bak" "*.tmp" "*.log" "*.swp" "*~"
        "requirements.txt" "package.json" "package-lock.json"
        "setup.py" "setup.cfg" "pyproject.toml"
        "Dockerfile" "docker-compose.yml" ".dockerignore"
        "Makefile" ".env.example" "*.sample"
        "Screenshot_*.png" "*.jpg" "*.jpeg"
    )
    for pat in "${patterns[@]}"; do
        while IFS= read -r -d '' f; do
            if rm -rf "$f" 2>/dev/null; then
                ok "Removed: $(basename "$f")"; cleaned=$((cleaned+1))
            fi
        done < <(find "$INSTALL_DIR" -maxdepth 2 -name "$pat" -print0 2>/dev/null)
    done
    while IFS= read -r -d '' d; do
        rm -rf "$d" 2>/dev/null && ok "Removed cache: $(basename "$d")" && cleaned=$((cleaned+1))
    done < <(find "$INSTALL_DIR" -type d \( -name "__pycache__" -o -name ".pytest_cache" \) -print0 2>/dev/null)
    if [ "$cleaned" -eq 0 ]; then ok "Nothing to clean."; else ok "Cleaned $cleaned item(s)."; fi
}

# ---------- Shortcuts (auto, not a menu option) ----------
create_shortcuts() {
    header "Creating Shortcuts"

    # 1) Terminal command: lauda
    mkdir -p "$BIN_DIR"
    cat > "$BIN_DIR/lauda" <<EOF
#!/bin/bash
exec python3 "$LAUDA_PY" "\$@"
EOF
    chmod +x "$BIN_DIR/lauda"
    ok "Terminal command installed: lauda"

    # 2) Ensure ~/.local/bin is on PATH (persist to shell rc files)
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        local export_line='export PATH="$HOME/.local/bin:$PATH"'
        local added_to=""

        for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
            # create the rc file if it doesn't exist and this shell uses it
            case "$rc" in
                "$HOME/.bashrc") [ -f "$rc" ] || [ "$SHELL" = "/bin/bash" ] || [ "$SHELL" = "/usr/bin/bash" ] || continue ;;
                "$HOME/.zshrc")  [ -f "$rc" ] || [ "$SHELL" = "/bin/zsh" ] || [ "$SHELL" = "/usr/bin/zsh" ] || continue ;;
                "$HOME/.profile") [ -f "$rc" ] || continue ;;
            esac
            if ! grep -qF 'HOME/.local/bin' "$rc" 2>/dev/null; then
                printf '\n# Added by Lauda Code installer\n%s\n' "$export_line" >> "$rc"
                added_to="$added_to $(basename "$rc")"
            fi
        done

        if [ -n "$added_to" ]; then
            ok "Added $BIN_DIR to PATH in:$added_to"
            export PATH="$BIN_DIR:$PATH"
        else
            warn "Could not auto-add PATH. Add manually:"
            echo "  echo '$export_line' >> ~/.bashrc"
        fi
    else
        ok "PATH already includes $BIN_DIR"
    fi

    # 3) Desktop entry + application menu
    mkdir -p "$APPS_DIR"
    local desktop_file="$APPS_DIR/lauda-code.desktop"
    cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=Lauda Code
Comment=Professional AI Coding Agent
Exec=$BIN_DIR/lauda
Icon=utilities-terminal
Terminal=true
Categories=Development;Utility;
Keywords=AI;Code;Lauda;
EOF
    chmod +x "$desktop_file"
    ok "App menu shortcut created."

    # 4) Desktop shortcut (if Desktop dir exists)
    if [ -d "$DESKTOP_DIR" ]; then
        cp "$desktop_file" "$DESKTOP_DIR/lauda-code.desktop"
        chmod +x "$DESKTOP_DIR/lauda-code.desktop"
        gio set "$DESKTOP_DIR/lauda-code.desktop" metadata::trusted true 2>/dev/null || true
        ok "Desktop shortcut created."
    fi
}

# ---------- Check Updates ----------
check_updates() {
    header "Check for Updates"
    local local_v=$(get_local_version)
    log "Installed version: $local_v"

    if ! has curl; then fail "curl not found."; return 1; fi

    log "Fetching version info from GitHub..."
    local json
    json=$(curl -fsSL "$VERSION_JSON_URL" 2>/dev/null) || { fail "Could not reach GitHub."; return 1; }

    local remote_v
    remote_v=$(echo "$json" | grep -oE '"version"[[:space:]]*:[[:space:]]*"[^"]+"' \
                          | head -n1 | sed -E 's/.*"([^"]+)"$/\1/')
    local changelog
    changelog=$(echo "$json" | grep -oE '"changelog"[[:space:]]*:[[:space:]]*"[^"]+"' \
                          | head -n1 | sed -E 's/.*"([^"]+)"$/\1/')

    if [ -z "$remote_v" ]; then fail "Invalid version.json format."; return 1; fi

    log "Latest version:   $remote_v"
    if [ -n "$changelog" ]; then echo -e "  ${CYAN}◈ Changelog:${NC} $changelog"; fi

    if [ "$remote_v" = "$local_v" ]; then
        ok "You are up to date."
        return 0
    fi

    echo
    warn "New version available: $local_v → $remote_v"
    local a=""
    read_tty a "↳ Update now? [Y/n]: " || a=""
    a=${a:-Y}
    if [[ "$a" =~ ^[Yy]$ ]]; then
        do_update "$remote_v"
    fi
}

# ---------- Perform Update ----------
do_update() {
    local new_v="$1"
    header "Updating Lauda Code"
    log "Pulling latest changes from Git..."
    if git -C "$INSTALL_DIR" pull origin main 2>/dev/null; then
        echo "$new_v" > "$VERSION_FILE"
        ok "Updated to $new_v"
    else
        fail "Git pull failed. Try reinstalling."
    fi
}

# ---------- Install / Reinstall (auto-creates shortcuts) ----------
install_tool() {
    header "Installing Lauda Code"
    mkdir -p "$INSTALL_DIR" "$BIN_DIR"

    clone_repo

    if [ ! -f "$LAUDA_PY" ]; then
        fail "lauda_code.py not found in the repository!"
        return 1
    fi

    get_local_version > "$VERSION_FILE"

    # Shortcuts are ALWAYS created as part of install — no prompt, no menu option
    create_shortcuts
    clean_unwanted

    ok "Lauda Code installed at $INSTALL_DIR"
    return 0
}

# ---------- Run ----------
run_lauda() {
    header "Run Lauda Code"
    if [ ! -f "$LAUDA_PY" ]; then
        fail "Lauda Code not installed. Choose Install/Reinstall first."
        pause; return
    fi
    log "Starting Lauda Code..."
    echo
    python3 "$LAUDA_PY" "$@" || fail "Lauda exited with error."
    pause
}

# ---------- About ----------
show_about() {
    header "About"
    cat <<EOF
${BOLD}Lauda Code${NC} — Professional AI Coding Agent
Version: $(get_local_version)

${BOLD}Developed by:${NC} ERROR
${BOLD}Telegram:${NC}    https://t.me/aab_ho_ga_comeback
${BOLD}GitHub:${NC}      ERROR0101r

${BOLD}Features:${NC}
 ◈ Multi-provider (OpenRouter, Groq, Cerebras, Mistral, Gemini)
 ◈ Smart fallback + token tracking
 ◈ Autopilot mode + Web UI (port 8080)
 ◈ Sandboxed file/command tools

${BOLD}Usage:${NC}
  Type ${CYAN}lauda${NC} in any terminal to launch.
  Or run option ${CYAN}1${NC} from this menu.
EOF
    pause
}

# ---------- Ensure Installed ----------
ensure_installed() {
    if [ ! -f "$LAUDA_PY" ]; then
        warn "Lauda Code not found — installing first..."
        install_tool || { fail "Install failed."; exit 1; }
    fi
}

# ---------- Menu ----------
main_menu() {
    clear 2>/dev/null || printf "\033c"
    echo -e "${MAGENTA}${BOLD}"
    cat <<'EOF'
  ╔═════════════════════════════════════╗
  ║        LAUDA CODE • LAUNCHER        ║
  ╚═════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo -e "  ${CYAN}1)${NC} 🚀 Run Lauda Code"
    echo -e "  ${CYAN}2)${NC} 🔄 Check for Updates"
    echo -e "  ${CYAN}3)${NC} ℹ️  About"
    echo -e "  ${CYAN}4)${NC} 🔧 Reinstall / Repair"
    echo -e "  ${CYAN}5)${NC} 🧹 Clean Unwanted Files"
    echo -e "  ${CYAN}6)${NC} ❌ Exit"
    echo

    if ! have_tty; then
        fail "No controlling terminal available."
        echo "  Run this script directly from an interactive shell:"
        echo "    bash lauda.sh"
        exit 1
    fi

    local choice=""
    if ! read_tty choice "↳ Select option [1-6]: "; then
        echo
        exit 0
    fi

    if [[ -z "$choice" ]]; then
        return
    fi

    case "$choice" in
        1) ensure_installed; run_lauda ;;
        2) check_updates; pause ;;
        3) show_about ;;
        4) install_tool; pause ;;
        5) clean_unwanted; pause ;;
        6) exit 0 ;;
        *) warn "Invalid choice: '${choice}'"; sleep 1 ;;
    esac
}

# ---------- Entry ----------
clear 2>/dev/null || printf "\033c"
echo -e "${BOLD}${CYAN}🚀 Lauda Code Setup${NC}"
echo -e "${YELLOW}◈ Developed by ERROR · TG: t.me/aab_ho_ga_comeback${NC}\n"

if ! have_tty; then
    fail "No controlling terminal detected."
    echo "  Download and run instead of piping:"
    echo "    curl -fsSL <url> -o lauda.sh && bash lauda.sh"
    exit 1
fi

check_dependencies
clone_repo

# First-time install: shortcuts are created here, automatically
if [ ! -f "$LAUDA_PY" ]; then
    warn "First-time setup — installing Lauda Code..."
    install_tool
fi

while true; do
    main_menu
done
