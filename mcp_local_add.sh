#!/bin/bash
source .env
claude mcp add-json "meta-ads-local" '{"command":"'$(pwd)'/mcp_env/bin/meta-ads-mcp","env":{"FACEBOOK_ACCESS_TOKEN":"'$FACEBOOK_ACCESS_TOKEN'"}}'
