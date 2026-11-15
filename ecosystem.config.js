// Paths are derived, not written out: the checkout is wherever this file is, and logs go
// to ~/logs. Adjust LOG_FILE if your host keeps logs elsewhere.
const os = require("os");
const path = require("path");

const LOG_FILE = path.join(os.homedir(), "logs", "memory-metadata-mcp.log");

module.exports = {
  apps: [{
    name: "memory-metadata-mcp",
    // src/ layout + console entry point. The venv is built fresh from uv.lock, non-editable,
    // with the interpreter pinned and the checkout verified: README "Installation".
    // The `-m` form matches the memsearch-mcp sibling; `memory-metadata-mcp` (the
    // console script) is an equivalent launch once the package is installed.
    script: "/opt/venvs/memory-metadata-mcp/bin/python3",
    args: ["-m", "memory_metadata_mcp.server"],
    cwd: __dirname,
    interpreter: "none",

    restart_delay: 5000,
    max_restarts: 10,
    min_uptime: "10s",

    out_file: LOG_FILE,
    error_file: LOG_FILE,
    merge_logs: true,
    time: true,

    env: {
      LOG_LEVEL: "INFO",
      MEMORY_METADATA_HOST: "127.0.0.1",
      MEMORY_METADATA_PORT: "8490",
      // MEMORY_METADATA_DB defaults to ~/.claude/memory/.metadata.db
    },
  }]
};
