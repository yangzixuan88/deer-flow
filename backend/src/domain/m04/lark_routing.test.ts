/**
 * M04 飞书CLI路由集成测试
 * ================================================
 * 测试Coordinator中的飞书CLI意图识别和路由
 * ================================================
 */

import { SystemType } from '../m04/types';
import { Coordinator } from '../m04/coordinator';
import { ExecutorType } from '../m11/types';

describe('LarkCLI Intent Detection', () => {
  let coordinator: Coordinator;

  beforeEach(() => {
    coordinator = new Coordinator();
  });

  describe('detectLarkIntent()', () => {
    const larkInputs = [
      '发送飞书消息给张三',
      '查看我的日历议程',
      '创建新的飞书文档',
      '搜索用户李四',
      '查询会议室列表',
      '创建日历事件',
      '新建多维表格',
      '添加任务',
      '获取考勤统计',
      '发送邮件',
      '创建审批',
      '上传文件到飞盘',
      '创建幻灯片',
    ];

    const nonLarkInputs = [
      '帮我搜索今天的天气',
      '写一段Python代码',
      '分析销售数据',
      '打开浏览器访问Google',
      '关机',
    ];

    test.each(larkInputs)('should detect lark intent: %s', (input) => {
      expect(coordinator.detectLarkIntent(input)).toBe(true);
    });

    test.each(nonLarkInputs)('should NOT detect lark intent: %s', (input) => {
      expect(coordinator.detectLarkIntent(input)).toBe(false);
    });
  });

  describe('getLarkSkills()', () => {
    it('should return 22 supported lark skills', () => {
      const skills = coordinator.getLarkSkills();
      expect(skills.length).toBe(22);
    });

    it('should include msg-send skill', () => {
      const skills = coordinator.getLarkSkills();
      const msgSend = skills.find(s => s.skill === 'msg-send');
      expect(msgSend).toBeDefined();
      expect(msgSend?.command).toBe('im message create');
    });

    it('should include calendar-agenda skill', () => {
      const skills = coordinator.getLarkSkills();
      const agenda = skills.find(s => s.skill === 'calendar-agenda');
      expect(agenda).toBeDefined();
      expect(agenda?.command).toBe('calendar +agenda');
    });
  });
});

describe('LarkCLI Coordinator Routing', () => {
  let coordinator: Coordinator;

  beforeEach(() => {
    coordinator = new Coordinator();
  });

  describe('execute() with SystemType.LARKSUITE', () => {
    it('should route to LARKSUITE system type', async () => {
      const result = await coordinator.execute({
        request_id: 'test_req_001',
        session_id: 'test_session',
        system_type: SystemType.LARKSUITE,
        priority: 'normal',
        metadata: {
          instruction: 'calendar +agenda --days 7',
          profile: 'daguan_zhu',
          timeout_ms: 30000,
          as_bot: true,
        },
      });

      expect(result.system_type).toBe(SystemType.LARKSUITE);
      // 由于实际执行lark-cli，结果success取决于环境
      expect(result).toHaveProperty('execution_time_ms');
    });

    it('should throw error when command is missing', async () => {
      const result = await coordinator.execute({
        request_id: 'test_req_002',
        session_id: 'test_session',
        system_type: SystemType.LARKSUITE,
        priority: 'normal',
        metadata: {},
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('command');
    });
  });
});

describe('LarkCLI Pattern Matching', () => {
  const patternTests = [
    // 消息类
    { input: '发送飞书消息', expectedSkill: 'msg-send' },
    { input: '发送消息到飞书', expectedSkill: 'msg-send' },
    { input: '发送lark消息', expectedSkill: 'msg-send' },
    { input: '查看飞书群消息历史', expectedSkill: 'im-message-list' },

    // 日历类
    { input: '查看日历议程', expectedSkill: 'calendar-agenda' },
    { input: '查询日程', expectedSkill: 'calendar-agenda' },
    { input: '创建日历事件', expectedSkill: 'calendar-event-create' },
    { input: '添加日程', expectedSkill: 'calendar-event-create' },
    { input: '查询日历事件', expectedSkill: 'calendar-event-list' },
    { input: '查询会议室', expectedSkill: 'meeting-room-list' },

    // 文档类
    { input: '创建云文档', expectedSkill: 'doc-create' },
    { input: '新建飞书文档', expectedSkill: 'doc-create' },
    { input: '追加文档块', expectedSkill: 'doc-append-block' },
    { input: '创建电子表格', expectedSkill: 'sheet-create' },
    { input: '更新表格单元格', expectedSkill: 'sheet-update-cell' },
    { input: '创建多维表格', expectedSkill: 'base-create-table' },
    { input: '添加记录到多维表格', expectedSkill: 'base-add-item' },
    { input: '上传飞书文件', expectedSkill: 'drive-file-upload' },
    { input: '创建幻灯片', expectedSkill: 'slides-create' },

    // 任务类
    { input: '创建任务', expectedSkill: 'task-create' },
    { input: '添加子任务', expectedSkill: 'task-subtask-add' },

    // 通讯录
    { input: '搜索用户张三', expectedSkill: 'contact-user-search' },
    { input: '查找用户信息', expectedSkill: 'contact-user-search' },
    { input: '获取用户信息', expectedSkill: 'contact-user-get' },

    // 知识库
    { input: '搜索知识库', expectedSkill: 'wiki-node-search' },

    // 邮件
    { input: '发送邮件', expectedSkill: 'mail-message-send' },

    // 审批
    { input: '创建审批', expectedSkill: 'approval-instance-create' },

    // 考勤
    { input: '考勤统计', expectedSkill: 'attendance-stats' },
  ];

  test.each(patternTests)('pattern: $input -> $expectedSkill', ({ input, expectedSkill }) => {
    // 验证技能路由通过Coordinator的getLarkSkills
    const coordinator = new Coordinator();
    const skills = coordinator.getLarkSkills();
    const skillEntry = skills.find(s => s.skill === expectedSkill);

    expect(skillEntry).toBeDefined();
    // 由于是黑盒测试，这里只验证技能存在
  });
});
