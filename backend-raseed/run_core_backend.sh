#!/bin/bash

# Run start_mcp_system.py in the background and log output
python3 start_mcp_system.py > start_mcp_system.log 2>&1 &
START_MCP_PID=$!
echo "start_mcp_system.py started with PID $START_MCP_PID"

# Run pipeline_api.py in the background and log output
python3 pipeline_api.py > pipeline_api.log 2>&1 &
PIPELINE_API_PID=$!
echo "pipeline_api.py started with PID $PIPELINE_API_PID"

# Wait for both processes to finish
wait $START_MCP_PID $PIPELINE_API_PID 