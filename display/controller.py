from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.lcd.device import st7735
from PIL import ImageFont
from time import sleep

class DisplayController:
    def __init__(self, context, button_up, button_down, button_left, button_right):
        self.context = context
        self.scroll_x = 0
        self.scroll_index = 0
        self.max_lines = 3
        self.data_lines = []
        self.button_up = button_up
        self.button_down = button_down
        self.button_left = button_left
        self.button_right = button_right
        self.button_up.when_pressed = self.update_scroll_y_up
        self.button_down.when_pressed = self.update_scroll_y_down
        self.button_left.when_pressed = self.update_scroll_x_left
        self.button_right.when_pressed = self.update_scroll_x_right

    def update_scroll_x_left(self):
        self.scroll_x = max(0, self.scroll_x - 20)

    def update_scroll_x_right(self):
        max_scroll_x = self.update_max_scroll_x()
        self.scroll_x = min(max_scroll_x, self.scroll_x + 20)

    def update_scroll_y_up(self):
        if len(self.data_lines) > self.max_lines:
            self.scroll_index = max(0, self.scroll_index - 1)

    def update_scroll_y_down(self):
        if len(self.data_lines) > self.max_lines:
            self.scroll_index = min(len(self.data_lines) - self.max_lines, self.scroll_index + 1)

    def get_max_content_width(self, data_lines, font_path, font_size, serial_display_width):
        font = ImageFont.truetype(font_path, font_size)
        max_width = 0
        for line in data_lines:
            try:
                label, value = line.split(": ", 1)
            except ValueError:
                value = line
            width = font.getlength(value)
            if width > max_width:
                max_width = width
        return max_width

    def update_max_scroll_x(self):
        c = self.context
        max_content_width = self.get_max_content_width(
            self.data_lines, c.font_path, c.config['font_size'], c.config.get('serial_display_width', 128)
        )
        return max(0, int(max_content_width - c.config.get('serial_display_width', 128) + 10))

    def serial_displays(self):
        c = self.context
        if c.config['serial_display_type'] == 'lcd_st7735':
            DISPLAY_WIDTH = c.config.get('serial_display_width', 128)
            DISPLAY_HEIGHT = c.config.get('serial_display_height', 128)
            DISPLAY_ROTATE = c.config.get('serial_display_rotate', 0)
            DISPLAY_HORIZONTAL_OFFSET = c.config.get('serial_display_horizontal_offset', 1)
            DISPLAY_VERTICAL_OFFSET = c.config.get('serial_display_vertical_offset', 2)
            DISPLAY_BACKGROUND = str(c.config.get('serial_display_background', True))
            x = 0
            serial = spi(device=0, port=0, bus_speed_hz=8000000, transfer_size=4096, gpio_DC=25, gpio_RST=27)
            device = st7735(serial, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT,
                            h_offset=DISPLAY_HORIZONTAL_OFFSET, v_offset=DISPLAY_VERTICAL_OFFSET,
                            bgr=DISPLAY_BACKGROUND, persist=False, rotate=DISPLAY_ROTATE)
            while not c.stop_event.is_set():
                lldp = c.redis_db.hgetall('LLDP')
                self.data_lines = []
                if c.config.get("show_chassis_id", False): self.data_lines.append(f"Chassis ID: {lldp.get('chassis_id', '-')}")
                if c.config.get("show_port_id", False): self.data_lines.append(f"Port ID: {lldp.get('port_id', '-')}")
                if c.config.get("show_vlan_id", False): self.data_lines.append(f"VLAN ID: {lldp.get('vlan_id', '-')}")
                if c.config.get("show_chassis_description", False): self.data_lines.append(f"Description: {lldp.get('chassis_description', '-')}")
                if c.config.get("show_port_descr", False): self.data_lines.append(f"Port Description: {lldp.get('port_descr', '-')}")
                if c.config.get("show_auto_neg_current", False): self.data_lines.append(f"Current Mode: {lldp.get('auto_neg_current', '-')}")
                if c.config.get("show_auto_supported", False): self.data_lines.append(f"Auto Support: {lldp.get('auto_supported', '-')}")
                if c.config.get("show_auto_enabled", False): self.data_lines.append(f"Auto Enable: {lldp.get('auto_enabled', '-')}")
                if c.config.get("show_available_modes_str", False): self.data_lines.append(f"Available Modes: {lldp.get('available_modes_str', '-')}")
                if c.config.get("show_power_supported", False): self.data_lines.append(f"Power Support: {lldp.get('power_supported', '-')}")
                if c.config.get("show_power_enabled", False): self.data_lines.append(f"Power Enabled: {lldp.get('power_enabled', '-')}")
                if c.config.get("show_device_type", False): self.data_lines.append(f"Device Type: {lldp.get('lldp_med_device_type', '-')}")
                if c.config.get("show_management_ip", False): self.data_lines.append(f"Management IP: {lldp.get('management_ip', '-')}")
                visible_lines = self.data_lines[self.scroll_index:self.scroll_index + self.max_lines]
                with canvas(device) as draw:
                    font = ImageFont.truetype(c.font_path, c.config['font_size'])
                    y_offset = 25
                    line_spacing = c.config['font_size'] + 1
                    if c.config.get('use_ups_hat', False):
                        battery_power = c.redis_db.get('battery_power')
                        draw.text((x+1, 0), f"Battery {battery_power}%", font=font, fill="yellow")
                    for i, line in enumerate(visible_lines, start=0):
                        try:
                            label, value = line.split(": ")
                        except ValueError:
                            label, value = line, ""
                        x_position = x+1 - self.scroll_x
                        y_position = y_offset + (line_spacing * 2 * i)
                        draw.text((x_position, y_position), label, font=font, fill="lime")
                        draw.text((x_position, y_position + line_spacing), f"{value}", font=font, fill="cyan")
                sleep(1 / c.config['serial_display_refresh_rate'])
