/**
 * SkillRouter 集成测试
 */
import { SkillRouter, skillRouter } from './skill_router';

describe('SkillRouter', () => {
  describe('route()', () => {
    const testCases: { intent: string; expected: string }[] = [
      // 代码审查
      { intent: '代码审查', expected: '/review' },
      { intent: '帮我审查代码', expected: '/review' },
      { intent: 'code review', expected: '/review' },
      // QA 测试
      { intent: '测试用例', expected: '/qa' },
      { intent: 'run tests', expected: '/qa' },
      // 发布部署
      { intent: '部署', expected: '/ship' },
      { intent: 'deploy', expected: '/ship' },
      // 产品构思
      { intent: '产品创意', expected: '/office-hours' },
      // 调试调查
      { intent: '调查问题', expected: '/investigate' },
      { intent: 'investigate', expected: '/investigate' },
      // 架构评审
      { intent: '架构评审', expected: '/plan-eng-review' },
      // 安全
      { intent: '危险操作警告', expected: '/careful' },
    ];

    testCases.forEach(({ intent, expected }) => {
      it(`"${intent}" → ${expected}`, () => {
        const result = skillRouter.route(intent);
        expect(result).not.toBeNull();
        expect(result!.skill).toBe(expected);
      });
    });

    it('不匹配的意图返回 null', () => {
      const result = skillRouter.route('这是一个完全随机的请求 xyz123');
      expect(result).toBeNull();
    });
  });

  describe('getAllSkills()', () => {
    it('返回所有注册的 skills', () => {
      const skills = skillRouter.getAllSkills();
      expect(skills.length).toBeGreaterThan(0);
    });
  });

  describe('routeAndBuild()', () => {
    it('返回匹配的 instruction', () => {
      const result = skillRouter.routeAndBuild('代码审查', '审查 src/domain');
      expect(result.matched).toBe(true);
      expect(result.skill).toBe('/review');
      expect(result.instruction).toContain('/review');
      expect(result.instruction).toContain('审查 src/domain');
    });

    it('不匹配返回 matched: false', () => {
      const result = skillRouter.routeAndBuild('随机请求 abc', '');
      expect(result.matched).toBe(false);
    });
  });
});
