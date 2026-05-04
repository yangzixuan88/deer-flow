/**
 * Oracle (咨询者) 三重核实规则集 (RuleSet)
 * 严格对标《超级宪法》§2.3/§3.4 置信度 < 0.7 熔断逻辑
 */

export const OracleAuditRules = {
  version: "2.0",
  thresholds: {
    confidence_melt: 0.7, // 宪法强制熔断位
    auto_pass: 0.95      // 自动通过位
  },
  
  // 三层核实流程 (Triple-Check Loop)
  verification_layers: [
    {
      id: "L1_Executor_SelfCheck",
      role: "Hephaestus",
      objective: "执行者自我对比计划与输出的一致性",
      action: "semantic_similarity_check"
    },
    {
      id: "L2_Knowledge_Validator",
      role: "Librarian",
      objective: "核实输出内容是否符合搜索阶段获取的客观事实",
      action: "fact_check_against_search_results"
    },
    {
      id: "L3_Critical_Reviewer",
      role: "Oracle",
      objective: "作为最终批判者寻找逻辑漏洞或潜在安全风险",
      action: "red_teaming_audit"
    }
  ],

  // 熔断决策逻辑
  on_audit_failure: {
    action: "suspend_and_escalate",
    notification_tier: "Tier_2_Red_Card",
    feedback_loop: "ICE_Intent_Clarification"
  }
};
