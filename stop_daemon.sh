if [ -f /tmp/server_daemon.pid ]; then
    kill $(cat /tmp/server_daemon.pid)
fi

if [ -f /tmp/server_stderr.log ]; then
    rm /tmp/server_stderr.log
fi

if [ -f /tmp/server_stdout.log ]; then
    rm /tmp/server_stdout.log
fi

if [ -f /tmp/cert.pem ]; then
    rm /tmp/cert.pem
fi

if [ -f /tmp/key.pem ]; then
    rm /tmp/key.pem
fi

if [ -f /tmp/config.txt ]; then
    rm /tmp/config.txt
fi