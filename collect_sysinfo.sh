#!/bin/bash
# System info collection script for v2-1.8ghz benchmark

cd ~/secure-tunnel/v2-1.8ghz

echo "=== RASPBERRY PI SYSTEM INFORMATION ===" > system_info.txt
echo "Generated: $(date -Iseconds)" >> system_info.txt
echo "" >> system_info.txt

echo "=== HOSTNAME ===" >> system_info.txt
hostname >> system_info.txt
echo "" >> system_info.txt

echo "=== KERNEL ===" >> system_info.txt
uname -a >> system_info.txt
echo "" >> system_info.txt

echo "=== OS RELEASE ===" >> system_info.txt
cat /etc/os-release >> system_info.txt
echo "" >> system_info.txt

echo "=== CPU INFO ===" >> system_info.txt
cat /proc/cpuinfo >> system_info.txt
echo "" >> system_info.txt

echo "=== CPU FREQUENCY ===" >> system_info.txt
echo "Governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)" >> system_info.txt
echo "Current Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) kHz" >> system_info.txt
echo "Min Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq) kHz" >> system_info.txt
echo "Max Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq) kHz" >> system_info.txt
echo "Available Frequencies: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies 2>/dev/null || echo N/A)" >> system_info.txt
echo "Available Governors: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null || echo N/A)" >> system_info.txt
echo "" >> system_info.txt

echo "=== MEMORY ===" >> system_info.txt
cat /proc/meminfo | head -20 >> system_info.txt
echo "" >> system_info.txt

echo "=== TEMPERATURE ===" >> system_info.txt
vcgencmd measure_temp >> system_info.txt 2>/dev/null || echo "N/A" >> system_info.txt
echo "" >> system_info.txt

echo "=== VOLTAGE ===" >> system_info.txt
vcgencmd measure_volts core >> system_info.txt 2>/dev/null || echo "N/A" >> system_info.txt
echo "" >> system_info.txt

echo "=== GPU MEMORY ===" >> system_info.txt
vcgencmd get_mem gpu >> system_info.txt 2>/dev/null || echo "N/A" >> system_info.txt
echo "" >> system_info.txt

echo "=== THROTTLING STATUS ===" >> system_info.txt
vcgencmd get_throttled >> system_info.txt 2>/dev/null || echo "N/A" >> system_info.txt
echo "" >> system_info.txt

echo "=== I2C DEVICES (INA219 at 0x40) ===" >> system_info.txt
sudo i2cdetect -y 1 >> system_info.txt 2>/dev/null || echo "i2cdetect not available" >> system_info.txt
echo "" >> system_info.txt

echo "=== USB DEVICES ===" >> system_info.txt
lsusb >> system_info.txt 2>/dev/null || echo "N/A" >> system_info.txt
echo "" >> system_info.txt

echo "=== DISK USAGE ===" >> system_info.txt
df -h >> system_info.txt
echo "" >> system_info.txt

echo "=== PYTHON VERSION ===" >> system_info.txt
python3 --version >> system_info.txt
echo "" >> system_info.txt

echo "=== GIT INFO ===" >> system_info.txt
cd ~/secure-tunnel
echo "Commit: $(git rev-parse HEAD 2>/dev/null || echo N/A)" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt
echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo N/A)" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt
echo "" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt

echo "=== LIBOQS VERSION (via cenv) ===" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt
source ~/cenv/bin/activate
python -c "import oqs; print('liboqs:', oqs.oqs_version())" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt 2>/dev/null || echo "N/A" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt
echo "" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt

echo "=== INSTALLED PYTHON PACKAGES ===" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt
pip list | grep -E "(oqs|ascon|numpy|ina219)" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt 2>/dev/null || echo "N/A" >> ~/secure-tunnel/v2-1.8ghz/system_info.txt

echo ""
echo "System info collected!"
echo ""
cat ~/secure-tunnel/v2-1.8ghz/system_info.txt
