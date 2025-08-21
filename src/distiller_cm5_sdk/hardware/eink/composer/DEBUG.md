# E-ink Composer Debug Guide

## Overview

The E-ink Composer includes comprehensive debugging capabilities for both development and production troubleshooting.

## Quick Start

### Enable Debug Mode

1. **Via Environment Variable**:
   ```bash
   export EINK_COMPOSER_DEBUG=true
   export EINK_COMPOSER_LOG_LEVEL=DEBUG
   ```

2. **Via Systemd Service**:
   Edit `/etc/systemd/system/eink-web.service` and set:
   ```ini
   Environment="EINK_COMPOSER_DEBUG=true"
   ```

3. **Via Web UI**:
   - Press `Ctrl+Shift+D` to toggle debug mode
   - Press `F12` to show/hide debug console

## Debug Features

### Frontend Debugging

#### Keyboard Shortcuts
- `F12` - Toggle debug console
- `Ctrl+Shift+D` - Toggle debug mode
- `Ctrl+Shift+L` - Dump layer state
- `Ctrl+Shift+P` - Show performance statistics

#### Debug Console
The debug console shows:
- All console.log/error/warn messages
- API request/response logs
- Performance timing
- Layer operations
- Canvas rendering events

#### Visual Debugging
When debug mode is enabled:
- Canvas bounds are highlighted
- Center lines are shown
- Layer boundaries are visible
- Selection boxes show coordinates

### Backend Debugging

#### Logging Levels
- `DEBUG` - Detailed operation logging
- `INFO` - General information
- `WARNING` - Potential issues
- `ERROR` - Errors with stack traces

#### Performance Tracking
All operations are timed and logged:
```python
@timed_operation("operation_name")
def my_function():
    # Function is automatically timed
    pass
```

#### Error Context
Errors are logged with full context:
```python
debug_manager.log_error("operation", exception, {
    "user_id": user_id,
    "layer_count": len(layers)
})
```

## Debug API Endpoints

### Get Debug Status
```bash
curl http://localhost:5000/api/debug/status
```

Returns:
```json
{
    "debug_mode": true,
    "log_level": "DEBUG",
    "log_file": "/tmp/eink_composer/debug.log",
    "uptime_seconds": 120.5,
    "operation_count": 45,
    "performance_stats": {
        "render_layers": {
            "count": 10,
            "average": 0.025,
            "min": 0.020,
            "max": 0.035
        }
    }
}
```

### Toggle Debug Mode
```bash
curl -X POST http://localhost:5000/api/debug/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Get Layer State
```bash
curl http://localhost:5000/api/debug/layers
```

## Log Files

Logs are written to `/tmp/eink_composer/debug.log` by default.

### View Logs
```bash
# Follow logs in real-time
tail -f /tmp/eink_composer/debug.log

# View errors only
grep ERROR /tmp/eink_composer/debug.log

# View performance metrics
grep "Performance -" /tmp/eink_composer/debug.log
```

### Log Format
```
2024-01-15 10:23:45.123 [DEBUG] eink_composer: Operation #42: add_text_layer
  x: 10
  y: 20
  text: Hello World
```

## Testing Debug Features

Run the test script:
```bash
python src/distiller_cm5_sdk/hardware/eink/composer/test_debug.py
```

This tests:
- Logging at all levels
- Performance tracking
- Error handling with context
- State dumping
- Service integration
- Configuration loading

## Configuration

### Configuration File
Create `/opt/distiller-cm5-sdk/eink_composer_debug.conf`:
```ini
EINK_COMPOSER_DEBUG=true
EINK_COMPOSER_LOG_LEVEL=DEBUG
EINK_COMPOSER_LOG_FILE=/var/log/eink_composer.log
```

### Priority Order
1. Environment variables (highest)
2. Configuration file
3. Default values (lowest)

## Production Debugging

### Enable Temporarily
```bash
# Enable debug for current session
curl -X POST http://device-ip:5000/api/debug/toggle -d '{"enabled": true}'

# Check status
curl http://device-ip:5000/api/debug/status

# Export logs
curl http://device-ip:5000/api/debug/layers > debug_dump.json
```

### Performance Analysis
```bash
# Get performance stats
curl http://device-ip:5000/api/debug/status | jq '.performance_stats'

# Monitor slow operations
tail -f /tmp/eink_composer/debug.log | grep "Performance.*[1-9][0-9]\{2,\}ms"
```

## Troubleshooting

### Debug Mode Not Working
1. Check environment variables: `env | grep EINK_COMPOSER`
2. Check config file exists and is readable
3. Restart service: `sudo systemctl restart eink-web`
4. Check log file permissions: `ls -la /tmp/eink_composer/`

### Performance Issues
1. Enable debug mode
2. Press `Ctrl+Shift+P` in web UI
3. Check for slow operations in performance stats
4. Review log file for bottlenecks

### Layer State Issues
1. Press `Ctrl+Shift+L` to dump layer state
2. Check browser console for JavaScript errors
3. Compare frontend and backend state:
   ```bash
   curl http://localhost:5000/api/debug/layers
   ```

## Best Practices

1. **Development**: Always run with `EINK_COMPOSER_DEBUG=true`
2. **Production**: Keep debug off unless troubleshooting
3. **Log Rotation**: Set up logrotate for production systems
4. **Performance**: Monitor performance stats regularly
5. **Security**: Don't expose debug endpoints publicly