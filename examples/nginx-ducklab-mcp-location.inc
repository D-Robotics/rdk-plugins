    # RDK Duck Lab MCP plugin — streamable HTTP for remote MCP clients.
    # Token-authenticated upstream on loopback; see /etc/rdk-duck-lab-mcp.env.
    location /ducklab-mcp/ {
        proxy_pass http://127.0.0.1:18103/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 1h;
    }
    location = /ducklab-mcp/duck-lab-mcp.tgz {
        alias /opt/duck-lab-mcp-plugin.tgz;
        default_type application/gzip;
        add_header Content-Disposition 'attachment; filename="duck-lab-mcp-0.2.0.tgz"';
    }
    location = /ducklab-mcp/install.sh {
        alias /opt/duck-lab-mcp-install.sh;
        default_type text/x-shellscript;
    }
    location = /ducklab-mcp/duck-lab-qoder-plugin.zip {
        alias /opt/duck-lab-qoder-plugin.zip;
        default_type application/zip;
        add_header Content-Disposition "attachment; filename=\"duck-lab-qoder-plugin-0.2.0.zip\"";
    }
    location = /ducklab-mcp/marketplace.json {
        alias /opt/duck-lab-marketplace.json;
        default_type application/json;
    }
    location = /ducklab-mcp/duck-lab-rdkstudio-plugin.zip {
        alias /opt/duck-lab-rdkstudio-plugin.zip;
        default_type application/zip;
        add_header Content-Disposition "attachment; filename=\"duck-lab-rdkstudio-plugin-0.2.0.zip\"";
    }
    location = /ducklab-mcp/rdkstudio-version.json {
        alias /opt/duck-lab-rdkstudio-version.json;
        default_type application/json;
    }
    location = /ducklab-mcp/install-rdkstudio.sh {
        alias /opt/duck-lab-mcp-install-rdkstudio.sh;
        default_type text/x-shellscript;
    }
