/**
 * M11 Governance Subprocess Entry Point
 * ====================================
 * Receives JSON commands from Python governance_bridge.py via stdin.
 * Invokes the appropriate R17-R19 subsystem and returns JSON result to stdout.
 *
 * Command format (from Python):
 *   {"command": "meta_governance_check", "payload": {...}, "timestamp": "..."}
 *
 * Response format (to Python):
 *   {"status": "ok", "result": {...}} | {"status": "error", "message": "..."}
 */

// Load all three rounds' engines
let metaEngine = null;
let cognitiveEngine = null;
let doctrineEngine = null;

try {
  const metaModule = await import(`./meta_governance_round17.ts`);
  metaEngine = metaModule.metaGovernanceEngine;
} catch (e) {
  // meta module not available
}

try {
  const cognitiveModule = await import(`./cognition_governance_round18.ts`);
  cognitiveEngine = cognitiveModule.cognitiveIntelligenceEngine;
} catch (e) {
  // cognitive module not available
}

try {
  const doctrineModule = await import(`./cognition_doctrine_round19.ts`);
  doctrineEngine = doctrineModule.cognitiveDoctrineEngine;
} catch (e) {
  // doctrine module not available
}

async function handleCommand(command, payload) {
  switch (command) {
    // ─────────────────────────────────────────
    // R17: Meta-Governance
    // ─────────────────────────────────────────
    case 'meta_governance_check': {
      if (!metaEngine) return { status: 'error', message: 'meta_governance not available' };
      // payload: {context: {decision_type, description, risk_level, stake_holders}}
      const ctx = payload.context || {};
      const decision = metaEngine.metaGovernance.checkGovernanceGate({
        decisionType: ctx.decision_type || 'unknown',
        description: ctx.description || '',
        riskLevel: ctx.risk_level || 'medium',
        stakeHolders: ctx.stake_holders || [],
      });
      return {
        status: 'ok',
        result: {
          allowed: decision.allowed,
          reason: decision.reason,
          patch_required: decision.requires_constitutional_patch,
        }
      };
    }

    case 'record_outcome': {
      // Record actual outcome for backflow into R17-R19 engines
      // payload: {outcome_type, actual, predicted, context}
      const outcomeType = payload.outcome_type || 'unknown';
      const actual = payload.actual;
      const predicted = payload.predicted;
      // Update cognitive engine with outcome
      if (cognitiveEngine && actual !== undefined && predicted !== undefined) {
        cognitiveEngine.processConflictingTruth(
          `outcome:${outcomeType}`,
          { id: payload.context?.source_id || 'system', value: predicted, confidence: 0.7 },
          { id: 'actual', value: actual, confidence: 1.0 }
        );
      }
      // Update doctrine engine reputation
      if (doctrineEngine && payload.context?.source_id) {
        doctrineEngine.processReputationUpdate(
          payload.context.source_id,
          predicted,
          actual
        );
      }
      return {
        status: 'ok',
        result: {
          allowed: true,
          reason: 'outcome_recorded',
          outcome_type: outcomeType,
        }
      };
    }

    case 'apply_rule_patch': {
      if (!metaEngine) return { status: 'error', message: 'meta_governance not available' };
      const patch = payload.patch || payload;
      const rules = metaEngine.constitutionalLayer.rules;
      // Find matching rule
      const targetRule = rules.find(r =>
        r.rule_id === patch.target_rule_id ||
        r.name.toLowerCase().includes((patch.rule_name || '').toLowerCase())
      );
      if (!targetRule) {
        return { status: 'ok', result: { status: 'rule_not_found', approved: false } };
      }
      const patchObj = {
        rule_id: `patch_${Date.now()}`,
        target_rule_id: targetRule.rule_id,
        patch_type: patch.patch_type || 'amendment',
        description: patch.description || '',
        risk_level: patch.risk_level || 'medium',
        status: 'pending',
      };
      const result = metaEngine.applyPatch(targetRule.rule_id, patchObj);
      return {
        status: 'ok',
        result: {
          status: result ? 'approved' : 'requires_review',
          patch_id: patchObj.rule_id,
          approved: result,
          allowed: result === true,
        }
      };
    }

    // ─────────────────────────────────────────
    // R18: Epistemic / Cognition
    // ─────────────────────────────────────────
    case 'epistemic_conflict_check': {
      if (!cognitiveEngine) return { status: 'error', message: 'cognitive_engine not available' };
      const truth = payload.truth || {};
      // payload: {truth: {value, source, confidence}}
      if (!truth.value || !truth.source) {
        return { status: 'ok', result: { has_conflict: false, resolution: 'insufficient_data', confidence_adjustment: 0 } };
      }
      // Register and check
      const result = cognitiveEngine.processConflictingTruth(
        truth.value,
        { id: truth.source, value: truth.confidence || 0.7, confidence: truth.confidence || 0.7 },
        truth.conflicting_source ? { id: truth.conflicting_source, value: truth.conflicting_value || 0.5, confidence: truth.conflicting_confidence || 0.7 } : undefined
      );
      return {
        status: 'ok',
        result: {
          has_conflict: result.truth.confidence < (truth.confidence || 0.7),
          resolution: result.decisionImpact,
          confidence_adjustment: result.truth.truth_confidence - (truth.confidence || 0.7),
        }
      };
    }

    case 'stakeholder_negotiation': {
      if (!cognitiveEngine) return { status: 'error', message: 'cognitive_engine not available' };
      const issue = payload.issue || {};
      if (!issue.description || !issue.positions) {
        return { status: 'ok', result: { decision: 'proceed', compromise: '', explanation: 'insufficient_data', escalated: false } };
      }
      const positions = new Map();
      for (const [k, v] of Object.entries(issue.positions)) {
        positions.set(k, v);
      }
      const result = cognitiveEngine.negotiateWithStakeholders(issue.description, positions);
      return {
        status: 'ok',
        result: {
          decision: result.decision,
          compromise: result.chosen_compromise || '',
          explanation: result.explanation || '',
          escalated: result.escalated_to_human || false,
        }
      };
    }

    case 'strategic_foresight': {
      if (!cognitiveEngine) return { status: 'error', message: 'cognitive_engine not available' };
      const scenario = payload.scenario || {};
      if (!scenario.description) {
        return { status: 'ok', result: { recommended_action: 'proceed', contingency_reserved: false, reasoning: 'insufficient_data' } };
      }
      const branches = (scenario.branches || []).map(b => ({
        name: b.name || 'branch',
        probability: b.probability || 0.3,
        gain: b.gain || 0.5,
        risk: b.risk || 0.5,
        confidence: b.confidence || 0.5,
        reversibility: b.reversibility || 0.5,
        triggers: b.triggers || [],
      }));
      const result = cognitiveEngine.analyzeScenarioWithForesight(
        scenario.mission_id || 'mission-unknown',
        scenario.description,
        scenario.horizon || 'medium',
        branches
      );
      return {
        status: 'ok',
        result: {
          recommended_action: result.recommended_present_action || 'proceed',
          contingency_reserved: result.reserved_contingency !== undefined,
          reasoning: result.reasoning || '',
        }
      };
    }

    // ─────────────────────────────────────────
    // R19: Identity / Reputation / Norm / Doctrine
    // ─────────────────────────────────────────
    case 'reputation_gate': {
      if (!doctrineEngine) return { status: 'error', message: 'doctrine_engine not available' };
      const source = payload.source || {};
      if (!source.source_id) {
        return { status: 'ok', result: { allowed: true, weight: 0.5, reputation_level: 'unknown', suppressed: false } };
      }
      const rep = doctrineEngine.identity.getReputation(source.source_id);
      if (!rep) {
        return { status: 'ok', result: { allowed: true, weight: source.base_weight || 0.5, reputation_level: 'unregistered', suppressed: false } };
      }
      const weight = doctrineEngine.getWeightedInput(source.source_id, source.base_weight || 0.5, 'balanced');
      return {
        status: 'ok',
        result: {
          allowed: rep.reputation_level !== 'suppressed',
          weight,
          reputation_level: rep.reputation_level,
          suppressed: rep.reputation_level === 'suppressed',
        }
      };
    }

    case 'norm_compliance': {
      if (!doctrineEngine) return { status: 'error', message: 'doctrine_engine not available' };
      const norm = payload.norm || {};
      if (!norm.behavior) {
        return { status: 'ok', result: { compliant: true, violated_norms: [], compliance_rate: 1.0 } };
      }
      const activeNorms = doctrineEngine.norm.getActiveNorms();
      const violatedNorms = [];
      for (const n of activeNorms) {
        const compliant = doctrineEngine.norm.checkCompliance(n.norm_id, norm.behavior);
        if (!compliant) violatedNorms.push(n.norm_id);
      }
      const complianceRate = activeNorms.length > 0
        ? (activeNorms.length - violatedNorms.length) / activeNorms.length
        : 1.0;
      return {
        status: 'ok',
        result: {
          compliant: violatedNorms.length === 0,
          violated_norms: violatedNorms,
          compliance_rate: complianceRate,
        }
      };
    }

    case 'doctrine_drift_check': {
      if (!doctrineEngine) return { status: 'error', message: 'doctrine_engine not available' };
      const signals = doctrineEngine.checkDriftAcrossDoctrines();
      return {
        status: 'ok',
        result: {
          has_drift: signals.length > 0,
          drifting_doctrines: signals.map(s => ({ doctrine_id: s.doctrine_id, drift_score: s.drift_score })),
          signals,
        }
      };
    }

    case 'evolve_doctrine': {
      if (!doctrineEngine) return { status: 'error', message: 'doctrine_engine not available' };
      const doc = payload.doctrine || {};
      if (!doc.doctrine_id) {
        return { status: 'ok', result: { status: 'insufficient_data', doctrine_id: null, evolved: false } };
      }
      const evolved = doctrineEngine.evolveDoctrine(doc.doctrine_id);
      return {
        status: 'ok',
        result: {
          status: evolved ? evolved.status : 'not_found',
          doctrine_id: doc.doctrine_id,
          evolved: evolved !== null,
        }
      };
    }

    case 'health_check': {
      return {
        status: 'ok',
        result: {
          meta_engine: metaEngine !== null,
          cognitive_engine: cognitiveEngine !== null,
          doctrine_engine: doctrineEngine !== null,
          timestamp: new Date().toISOString(),
        }
      };
    }

    default:
      return { status: 'error', message: `Unknown command: ${command}` };
  }
}

// Main: read JSON from stdin, write JSON to stdout
process.stdin.setEncoding('utf-8');
let data = '';
process.stdin.on('data', chunk => { data += chunk; });
process.stdin.on('end', async () => {
  try {
    const input = JSON.parse(data);
    const result = await handleCommand(input.command, input.payload);
    process.stdout.write(JSON.stringify(result, null, 0));
  } catch (e) {
    process.stdout.write(JSON.stringify({ status: 'error', message: e.message }));
  }
});
