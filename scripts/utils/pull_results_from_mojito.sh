#!/bin/bash
set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-$PWD/output}"
OUTPUT_DIR="${OUTPUT_DIR%/}"

if [ ! -d "$OUTPUT_DIR" ]; then
	echo "Output directory $OUTPUT_DIR does not exist. Creating it."
	mkdir -p "$OUTPUT_DIR"
fi

FELIPE_PASSWORD="${FELIPE_PASSWORD:-}"
MOJITO_PASSWORD="${MOJITO_PASSWORD:-}"

if ! command -v expect >/dev/null 2>&1; then
	echo "Error: expect is required but not installed." >&2
	exit 1
fi

export FELIPE_PASSWORD
export MOJITO_PASSWORD
export OUTPUT_DIR

expect <<'EOF'
set timeout -1
set felipe_pass $env(FELIPE_PASSWORD)
set mojito_pass $env(MOJITO_PASSWORD)
set output_dir $env(OUTPUT_DIR)
set ssh_cmd "ssh -o StrictHostKeyChecking=no -J ebalestra@felipe.dc.exa.unrc.edu.ar"
set cmd [list rsync -avz --progress -e $ssh_cmd --include=*/ --include=*.log --include=*.assertions --exclude=* inv@192.168.0.147:/home/inv/ebalestra/specvalid-deepseekr1/output/ "${output_dir}/"]
eval spawn $cmd
expect {
	-re "Are you sure you want to continue connecting.*" {
		send "yes\r"
		exp_continue
	}
	-re "ebalestra@felipe\\.dc\\.exa\\.unrc\\.edu\\.ar.*password:" {
		send "$felipe_pass\r"
		exp_continue
	}
	-re "inv@192\\.168\\.0\\.147.*password:" {
		send "$mojito_pass\r"
		exp_continue
	}
	eof
}
EOF
