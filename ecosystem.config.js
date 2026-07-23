module.exports = {
  apps: [{
    name: "memory-metadata-mcp",
    // src/ layout + console entry point: requires `pip install -e .` in the venv.
    // The `-m` form matches the memsearch-mcp sibling; `memory-metadata-mcp` (the
    // console script) is an equivalent launch once the package is installed.
    script: "/opt/venvs/memory-metadata-mcp/bin/python3",
    args: ["-m", "memory_metadata_mcp.server"],
    cwd: "/home/ted/repos/personal/memory-metadata-mcp",
    interpreter: "none",

    restart_delay: 5000,
    max_restarts: 10,
    min_uptime: "10s",

    out_file: "/home/ted/logs/memory-metadata-mcp.log",
    error_file: "/home/ted/logs/memory-metadata-mcp.log",
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
