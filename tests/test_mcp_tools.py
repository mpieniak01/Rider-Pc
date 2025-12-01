"""Tests for MCP Tools.

Testy jednostkowe narzędzi MCP: system, robot, weather, smart_home, git.
"""

import pytest
from unittest.mock import patch

from pc_client.mcp.tools import system, robot, weather, smart_home, git


class TestSystemTools:
    """Tests for system tools."""

    def test_get_time_returns_dict(self):
        """Test that get_time returns a dictionary with expected keys."""
        result = system.get_time()
        assert isinstance(result, dict)
        assert "time" in result
        assert "timezone" in result
        assert "timestamp" in result

    def test_get_time_returns_valid_timestamp(self):
        """Test that get_time returns a valid timestamp."""
        result = system.get_time()
        assert isinstance(result["timestamp"], int)
        assert result["timestamp"] > 0

    def test_get_system_status_returns_dict(self):
        """Test that get_system_status returns a dictionary."""
        result = system.get_system_status()
        assert isinstance(result, dict)
        assert "platform" in result
        assert "hostname" in result
        assert "python_version" in result


class TestRobotTools:
    """Tests for robot tools."""

    def test_get_robot_status_returns_dict(self):
        """Test that get_robot_status returns expected structure."""
        result = robot.get_robot_status()
        assert isinstance(result, dict)
        assert "connected" in result
        assert "battery" in result
        assert "mode" in result
        assert "position" in result

    def test_robot_move_valid_command(self):
        """Test robot_move with valid command."""
        result = robot.robot_move(command="forward", speed=50)
        assert result["executed"] is True
        assert result["command"] == "forward"
        assert result["speed"] == 50

    def test_robot_move_stop_command(self):
        """Test robot_move with stop command."""
        result = robot.robot_move(command="stop")
        assert result["executed"] is True
        assert result["mode"] == "idle"

    def test_robot_move_invalid_command(self):
        """Test robot_move with invalid command raises ValueError."""
        with pytest.raises(ValueError, match="Invalid command"):
            robot.robot_move(command="fly")

    def test_robot_move_invalid_speed(self):
        """Test robot_move with invalid speed raises ValueError."""
        with pytest.raises(ValueError, match="Speed must be between"):
            robot.robot_move(command="forward", speed=150)


class TestWeatherTools:
    """Tests for weather tools."""

    def test_get_weather_summary_returns_dict(self):
        """Test that get_weather_summary returns expected structure."""
        result = weather.get_weather_summary()
        assert isinstance(result, dict)
        assert "temperature" in result
        assert "location" in result
        assert "humidity" in result

    def test_get_weather_summary_custom_location(self):
        """Test that custom location is used when specified."""
        result = weather.get_weather_summary(location="Kraków, PL", use_cache=False)
        assert result["location"] == "Kraków, PL"


class TestSmartHomeTools:
    """Tests for smart_home tools."""

    def test_toggle_light_on(self):
        """Test turning light on."""
        result = smart_home.toggle_light(room="living_room", state=True)
        assert result["room"] == "living_room"
        assert result["light_on"] is True

    def test_toggle_light_off(self):
        """Test turning light off."""
        result = smart_home.toggle_light(room="bedroom", state=False)
        assert result["room"] == "bedroom"
        assert result["light_on"] is False

    def test_toggle_light_invalid_room(self):
        """Test toggle_light with invalid room raises ValueError."""
        with pytest.raises(ValueError, match="Unknown room"):
            smart_home.toggle_light(room="garage", state=True)

    def test_set_brightness(self):
        """Test setting brightness."""
        result = smart_home.set_brightness(room="kitchen", brightness=75)
        assert result["room"] == "kitchen"
        assert result["brightness"] == 75

    def test_set_brightness_invalid_room(self):
        """Test set_brightness with invalid room raises ValueError."""
        with pytest.raises(ValueError, match="Unknown room"):
            smart_home.set_brightness(room="cellar", brightness=50)

    def test_set_scene_morning(self):
        """Test activating morning scene."""
        result = smart_home.set_scene(scene="morning")
        assert result["scene"] == "morning"
        assert result["activated"] is True

    def test_set_scene_invalid(self):
        """Test set_scene with invalid scene raises ValueError."""
        with pytest.raises(ValueError, match="Unknown scene"):
            smart_home.set_scene(scene="party")

    def test_get_smart_home_status(self):
        """Test getting full smart home status."""
        result = smart_home.get_smart_home_status()
        assert "lights" in result
        assert "active_scene" in result
        assert "available_scenes" in result


class TestGitTools:
    """Tests for git tools."""

    @patch('pc_client.mcp.tools.git._run_git_command')
    def test_get_changed_files(self, mock_run):
        """Test get_changed_files returns expected structure."""
        mock_run.return_value = {
            "success": True,
            "stdout": "M  file1.py\nA  file2.py",
        }
        result = git.get_changed_files()
        assert "files" in result
        assert "count" in result
        assert result["count"] == 2

    @patch('pc_client.mcp.tools.git._run_git_command')
    def test_get_git_status(self, mock_run):
        """Test get_git_status returns expected structure."""
        mock_run.side_effect = [
            {"success": True, "stdout": "main"},
            {"success": True, "stdout": "abc123|commit msg|2 hours ago"},
            {"success": True, "stdout": "M file.py"},
            {"success": True, "stdout": "origin\thttps://github.com/..."},
        ]
        result = git.get_git_status()
        assert "current_branch" in result
        assert "last_commit" in result
        assert "is_git_repo" in result

    @patch('pc_client.mcp.tools.git._run_git_command')
    def test_get_diff(self, mock_run):
        """Test get_diff returns expected structure."""
        mock_run.return_value = {
            "success": True,
            "stdout": "diff --git a/file.py b/file.py\n+new line",
        }
        result = git.get_diff()
        assert "diff" in result
        assert "lines_count" in result

    @patch('pc_client.mcp.tools.git._run_git_command')
    def test_get_log(self, mock_run):
        """Test get_log returns expected structure."""
        mock_run.return_value = {
            "success": True,
            "stdout": "abc123|John|First commit|1 day ago\ndef456|Jane|Second commit|2 days ago",
        }
        result = git.get_log(count=5)
        assert "commits" in result
        assert "count" in result
        assert result["count"] == 2


class TestToolCallHandler:
    """Tests for MCP tool call handler."""

    def test_get_tools_for_llm(self):
        """Test get_tools_for_llm returns list of tools."""
        from pc_client.mcp.tool_call_handler import get_tools_for_llm
        tools = get_tools_for_llm()
        assert isinstance(tools, list)
        assert len(tools) > 0
        for tool in tools:
            assert "name" in tool
            assert "description" in tool

    def test_get_tools_prompt(self):
        """Test get_tools_prompt returns non-empty string."""
        from pc_client.mcp.tool_call_handler import get_tools_prompt
        prompt = get_tools_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "system.get_time" in prompt

    def test_parse_tool_call_valid_json(self):
        """Test parsing valid tool call JSON."""
        from pc_client.mcp.tool_call_handler import parse_tool_call
        response = '```json\n{"tool_call": {"name": "system.get_time", "arguments": {}}}\n```'
        result = parse_tool_call(response)
        assert result is not None
        assert result["name"] == "system.get_time"

    def test_parse_tool_call_no_tool(self):
        """Test parsing response without tool call."""
        from pc_client.mcp.tool_call_handler import parse_tool_call
        response = "This is just a normal text response."
        result = parse_tool_call(response)
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_tool_call(self):
        """Test executing a tool call."""
        from pc_client.mcp.tool_call_handler import execute_tool_call
        result = await execute_tool_call("system.get_time")
        assert result.ok is True
        assert result.tool == "system.get_time"
        assert "time" in result.result

    def test_format_tool_result_success(self):
        """Test formatting successful tool result."""
        from pc_client.mcp.tool_call_handler import format_tool_result
        from pc_client.mcp.registry import ToolInvokeResult
        result = ToolInvokeResult(
            ok=True,
            tool="system.get_time",
            result={"time": "2025-12-01T12:00:00"},
        )
        formatted = format_tool_result(result)
        assert "[Wynik narzędzia system.get_time]" in formatted

    def test_format_tool_result_error(self):
        """Test formatting failed tool result."""
        from pc_client.mcp.tool_call_handler import format_tool_result
        from pc_client.mcp.registry import ToolInvokeResult
        result = ToolInvokeResult(
            ok=False,
            tool="robot.move",
            error="Invalid command",
        )
        formatted = format_tool_result(result)
        assert "[Błąd narzędzia robot.move]" in formatted
