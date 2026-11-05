<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
          <span class="budget-value">{{ formatMoney(budget, 0) }}</span>
        </div>
        <input
          id="restocking-budget"
          v-model.number="budget"
          class="budget-slider"
          type="range"
          min="0"
          :max="maxBudget"
          :step="BUDGET_STEP"
          :aria-label="t('restocking.budgetLabel')"
          :disabled="maxBudget === 0"
        />
        <div class="budget-scale">
          <span>{{ formatMoney(0, 0) }}</span>
          <span>{{ formatMoney(maxBudget, 0) }}</span>
        </div>
        <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ formatMoney(budget, 0) }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.allocated') }}</div>
          <div class="stat-value">{{ formatMoney(allocated, 2) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatMoney(remaining, 2) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemCount') }}</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.longestLeadTime') }}</div>
          <div class="stat-value">{{ t('restocking.days', { days: longestLeadTime }) }}</div>
        </div>
      </div>

      <div v-if="submittedOrder" class="success-banner" role="status">
        <span>{{ t('restocking.successMessage', { orderNumber: submittedOrder.order_number }) }}</span>
        <router-link to="/orders" class="success-link">{{ t('restocking.viewOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="error" role="alert">{{ submitError }}</div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendations.length }})</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="recommendations.length === 0 || submitting || !!submittedOrder"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.submitting') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="candidates.length === 0" class="empty-state">
          {{ t('restocking.noCandidates') }}
        </div>
        <div v-else-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.empty') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.gap') }}</th>
                <th class="num">{{ t('restocking.table.recommendedQty') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="line in recommendations" :key="line.sku">
                <td><strong>{{ line.sku }}</strong></td>
                <td>{{ translateProductName(line.name) }}</td>
                <td>
                  <span :class="['badge', trendBadgeClass(line.trend)]">
                    {{ t(`trends.${line.trend}`) }}
                  </span>
                </td>
                <td class="num">{{ line.gap.toLocaleString() }}</td>
                <td class="num">
                  <strong>{{ line.quantity.toLocaleString() }}</strong>
                  <span v-if="line.partial" class="partial-note">/ {{ line.gap.toLocaleString() }}</span>
                </td>
                <td class="num">{{ formatMoney(line.unitCost, 2) }}</td>
                <td class="num"><strong>{{ formatMoney(line.lineTotal, 2) }}</strong></td>
                <td class="num">{{ t('restocking.days', { days: line.leadTimeDays }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

// Slider granularity and the bucket the slider max is rounded up to.
const BUDGET_STEP = 50
const BUDGET_ROUNDING = 500

// Lower number = higher restocking priority.
const TREND_PRIORITY = { increasing: 0, stable: 1, decreasing: 2 }

// Money math is done in integer cents so repeated subtraction never drifts
// (e.g. 0.1 + 0.2). The server rejects orders where total > budget, so the
// client total must never exceed the budget by a fraction of a cent.
const toCents = (amount) => Math.round(Number(amount) * 100)
const fromCents = (cents) => cents / 100

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const budget = ref(0)

    const submitting = ref(false)
    const submitError = ref(null)
    const submittedOrder = ref(null)

    // Items whose forecast exceeds current demand. Negative gaps (demand
    // falling below current level) are clamped to 0 and excluded.
    const candidates = computed(() => {
      return forecasts.value
        .map(f => ({
          sku: f.item_sku,
          name: f.item_name,
          trend: f.trend,
          gap: Math.max(Number(f.forecasted_demand) - Number(f.current_demand), 0),
          unitCents: toCents(f.unit_cost),
          leadTimeDays: Number(f.lead_time_days) || 0
        }))
        // A non-positive unit cost would make the greedy division meaningless.
        .filter(c => c.gap > 0 && c.unitCents > 0)
        .sort((a, b) => {
          const pa = TREND_PRIORITY[a.trend] ?? 3
          const pb = TREND_PRIORITY[b.trend] ?? 3
          if (pa !== pb) return pa - pb
          return b.gap - a.gap
        })
    })

    // Slider max = cost to fully close every gap, rounded UP to the next 500
    // so the full-coverage budget is always reachable on the slider.
    const maxBudget = computed(() => {
      const totalCents = candidates.value.reduce((sum, c) => sum + c.gap * c.unitCents, 0)
      return Math.ceil(fromCents(totalCents) / BUDGET_ROUNDING) * BUDGET_ROUNDING
    })

    // Greedy allocation over the priority-sorted candidates: each item takes as
    // many units as both its gap and the remaining budget allow. Allocation stops
    // at the first item the budget can't fully cover: that item gets a partial
    // quantity (floor of what is affordable) and is the last line. Lower-priority
    // items never jump ahead of an unfinished higher-priority one.
    const recommendations = computed(() => {
      let remainingCents = toCents(budget.value)
      const lines = []
      for (const c of candidates.value) {
        const affordable = Math.floor(remainingCents / c.unitCents)
        const quantity = Math.min(c.gap, affordable)
        // Can't afford even one unit of the current priority item: stop here.
        if (quantity <= 0) break
        const lineCents = quantity * c.unitCents
        remainingCents -= lineCents
        lines.push({
          sku: c.sku,
          name: c.name,
          trend: c.trend,
          gap: c.gap,
          quantity,
          partial: quantity < c.gap,
          unitCost: fromCents(c.unitCents),
          lineTotal: fromCents(lineCents),
          leadTimeDays: c.leadTimeDays
        })
        // A partially filled item is always the last line.
        if (quantity < c.gap) break
      }
      return lines
    })

    const allocated = computed(() => {
      return fromCents(recommendations.value.reduce((sum, l) => sum + toCents(l.lineTotal), 0))
    })

    const remaining = computed(() => fromCents(toCents(budget.value) - toCents(allocated.value)))

    // Items ship together, so the order arrives when the slowest item arrives.
    const longestLeadTime = computed(() => {
      return recommendations.value.reduce((max, l) => Math.max(max, l.leadTimeDays), 0)
    })

    const formatMoney = (amount, decimals = 2) => {
      return formatCurrencyWithDecimals(Number(amount) || 0, currentCurrency.value, decimals)
    }

    // Maps trend to shared badge colors: green / blue / yellow.
    const trendBadgeClass = (trend) => {
      const map = { increasing: 'success', stable: 'info', decreasing: 'warning' }
      return map[trend] || 'info'
    }

    const loadForecasts = async () => {
      try {
        loading.value = true
        error.value = null
        forecasts.value = await api.getDemandForecasts()
        // Default to half the max, snapped to the slider step.
        budget.value = Math.round((maxBudget.value * 0.5) / BUDGET_STEP) * BUDGET_STEP
      } catch (err) {
        error.value = `${t('restocking.loadError')}: ${err.message}`
        console.error('Failed to load demand forecasts:', err)
      } finally {
        loading.value = false
      }
    }

    // FastAPI returns `detail` as a string for HTTPException, or as an array of
    // validation errors for request-body schema failures.
    const extractErrorDetail = (err) => {
      const detail = err?.response?.data?.detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) return detail.map(d => d.msg).filter(Boolean).join('; ')
      return err?.message || ''
    }

    const placeOrder = async () => {
      if (recommendations.value.length === 0 || submitting.value) return
      submitting.value = true
      submitError.value = null
      submittedOrder.value = null
      try {
        submittedOrder.value = await api.createRestockingOrder({
          budget: budget.value,
          items: recommendations.value.map(l => ({ item_sku: l.sku, quantity: l.quantity }))
        })
      } catch (err) {
        const detail = extractErrorDetail(err)
        submitError.value = detail ? `${t('restocking.submitError')}: ${detail}` : t('restocking.submitError')
        console.error('Failed to submit restocking order:', err)
      } finally {
        submitting.value = false
      }
    }

    // A stale error no longer applies once the user adjusts the budget.
    // A new budget means new recommendations: clear the previous result so the
    // button is re-enabled for the new order (it stays disabled after a success
    // to prevent submitting the same order twice).
    watch(budget, () => {
      submitError.value = null
      submittedOrder.value = null
    })

    onMounted(loadForecasts)

    return {
      t,
      BUDGET_STEP,
      translateProductName,
      loading,
      error,
      budget,
      maxBudget,
      candidates,
      recommendations,
      allocated,
      remaining,
      longestLeadTime,
      submitting,
      submitError,
      submittedOrder,
      formatMoney,
      trendBadgeClass,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #2563eb;
  cursor: pointer;
}

.budget-slider:disabled {
  cursor: not-allowed;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.813rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.budget-hint {
  margin-top: 0.75rem;
  font-size: 0.875rem;
  color: #64748b;
}

.num {
  text-align: right;
}

.partial-note {
  margin-left: 0.25rem;
  color: #64748b;
  font-size: 0.813rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-size: 0.938rem;
}

.place-order-btn {
  padding: 0.5rem 1.25rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  color: #64748b;
  cursor: not-allowed;
}

.success-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
}

.success-link {
  color: #047857;
  font-weight: 600;
}
</style>
