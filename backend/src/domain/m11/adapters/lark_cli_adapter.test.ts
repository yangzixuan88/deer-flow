/**
 * M11 LarkCLI适配器集成测试
 * ================================================
 * 测试飞书CLI与ExecutorAdapter的集成
 * ================================================
 */

import { LarkCLIAdapter, larkCLIAdapter } from './lark_cli_adapter';
import { ExecutorAdapter, executorAdapter } from './executor_adapter';
import { ExecutorType } from '../types';

describe('LarkCLIAdapter', () => {
  describe('isAvailable()', () => {
    it('should check lark-cli availability', async () => {
      const available = await larkCLIAdapter.isAvailable();
      // lark-cli 可能未安装，测试应该宽容处理
      expect(typeof available).toBe('boolean');
    });
  });

  describe('getProfiles()', () => {
    it('should return configured profiles', () => {
      const profiles = larkCLIAdapter.getProfiles();
      expect(Array.isArray(profiles)).toBe(true);
      // 至少应该有 daguan_zhu
      expect(profiles).toContain('daguan_zhu');
    });
  });

  describe('getDefaultProfile()', () => {
    it('should return default profile', () => {
      const defaultProfile = larkCLIAdapter.getDefaultProfile();
      expect(defaultProfile).toBe('daguan_zhu');
    });
  });

  describe('parseSkillCommand()', () => {
    it('should parse msg-send command', () => {
      const result = larkCLIAdapter.parseSkillCommand('im message create --receive-id ou_xxx --content "hello"');
      expect(result.skill).toBe('msg-send');
      expect(result.action).toBe('im message create');
    });

    it('should parse calendar-agenda command', () => {
      const result = larkCLIAdapter.parseSkillCommand('calendar +agenda --days 7');
      expect(result.skill).toBe('calendar-agenda');
      expect(result.action).toBe('calendar +agenda');
    });

    it('should parse doc-create command', () => {
      const result = larkCLIAdapter.parseSkillCommand('drive doc create --title "Test Doc"');
      expect(result.skill).toBe('doc-create');
      expect(result.action).toBe('drive doc create');
    });
  });

  describe('execute() with real lark-cli', () => {
    it('should execute calendar agenda command', async () => {
      const result = await larkCLIAdapter.execute('calendar +agenda --days 1', {
        profile: 'daguan_zhu',
        timeout_ms: 30000,
        as_bot: true,
      });

      // 验证返回结构
      expect(result).toHaveProperty('success');
      expect(result).toHaveProperty('stdout');
      expect(result).toHaveProperty('stderr');
      expect(result).toHaveProperty('exit_code');
      expect(result).toHaveProperty('execution_time_ms');
    }, 60000);

    it('should handle invalid profile gracefully', async () => {
      const result = await larkCLIAdapter.execute('calendar +agenda', {
        profile: 'nonexistent_profile',
        timeout_ms: 10000,
        as_bot: true,
      });

      // 应当返回错误
      expect(result.success).toBe(false);
    }, 30000);
  });
});

describe('LarkCLI via ExecutorAdapter', () => {
  describe('submit and execute LARKSUITE_CLI', () => {
    it('should submit lark task and get task ID', async () => {
      const taskId = await executorAdapter.submit(
        ExecutorType.LARKSUITE_CLI,
        'calendar +agenda --days 1',
        {
          profile: 'daguan_zhu',
          timeout_ms: 30000,
          as_bot: true,
        },
        false // LarkCLI不过沙盒
      );

      expect(taskId).toBeTruthy();
      expect(taskId.startsWith('task_')).toBe(true);
    });

    it('should track LARKSUITE_CLI task status', async () => {
      const taskId = await executorAdapter.submit(
        ExecutorType.LARKSUITE_CLI,
        'im message create',
        { profile: 'daguan_zhu' },
        false
      );

      const status = executorAdapter.getTaskStatus(taskId);
      expect(status).toBe('idle');
    });
  });
});

describe('Skill Command Coverage', () => {
  const skillTests = [
    { cmd: 'im message create', expectedSkill: 'msg-send' },
    { cmd: 'im messages list --chat-id oc_xxx', expectedSkill: 'im-message-list' },
    { cmd: 'calendar +agenda --days 7', expectedSkill: 'calendar-agenda' },
    { cmd: 'calendar event create', expectedSkill: 'calendar-event-create' },
    { cmd: 'calendar events instance_view', expectedSkill: 'calendar-event-list' },
    { cmd: 'calendar meeting_room list', expectedSkill: 'meeting-room-list' },
    { cmd: 'drive doc create', expectedSkill: 'doc-create' },
    { cmd: 'drive doc block create', expectedSkill: 'doc-append-block' },
    { cmd: 'drive sheet create', expectedSkill: 'sheet-create' },
    { cmd: 'drive sheet cell update', expectedSkill: 'sheet-update-cell' },
    { cmd: 'drive bitable app create', expectedSkill: 'base-create-table' },
    { cmd: 'drive bitable record create', expectedSkill: 'base-add-item' },
    { cmd: 'task task create', expectedSkill: 'task-create' },
    { cmd: 'task subtask add', expectedSkill: 'task-subtask-add' },
    { cmd: 'contact +search-user --query "张三"', expectedSkill: 'contact-user-search' },
    { cmd: 'contact user get --user-id ou_xxx', expectedSkill: 'contact-user-get' },
    { cmd: 'wiki node search --query "keyword"', expectedSkill: 'wiki-node-search' },
    { cmd: 'drive file upload', expectedSkill: 'drive-file-upload' },
    { cmd: 'mail message create', expectedSkill: 'mail-message-send' },
    { cmd: 'approval instance create', expectedSkill: 'approval-instance-create' },
    { cmd: 'attendance user stats list', expectedSkill: 'attendance-stats' },
    { cmd: 'drive slides create', expectedSkill: 'slides-create' },
  ];

  test.each(skillTests)('skill $expectedSkill: $cmd', ({ cmd, expectedSkill }) => {
    const result = larkCLIAdapter.parseSkillCommand(cmd);
    expect(result.skill).toBe(expectedSkill);
  });
});
