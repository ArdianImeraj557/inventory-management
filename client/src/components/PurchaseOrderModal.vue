<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ mode === 'view' ? t('purchaseOrder.viewTitle') : t('purchaseOrder.createTitle') }}
            </h3>
            <button class="close-button" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <!-- Read-only backlog context, shown in both modes -->
            <div class="context-card">
              <div class="context-label">{{ t('purchaseOrder.backlogContext') }}</div>
              <div class="context-grid">
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.sku') }}</div>
                  <div class="info-value sku">{{ backlogItem.item_sku }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.itemName') }}</div>
                  <div class="info-value">{{ translateProductName(backlogItem.item_name) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.shortage') }}</div>
                  <div class="info-value danger">{{ shortage }} {{ t('purchaseOrder.units') }}</div>
                </div>
              </div>
            </div>

            <!-- Create mode -->
            <form v-if="mode === 'create'" id="po-form" class="po-form" @submit.prevent="submit">
              <div class="form-field full">
                <label for="po-supplier" class="form-label">
                  {{ t('purchaseOrder.supplierName') }} <span class="required">*</span>
                </label>
                <input
                  id="po-supplier"
                  v-model="form.supplierName"
                  type="text"
                  class="form-input"
                  :placeholder="t('purchaseOrder.supplierPlaceholder')"
                  required
                />
              </div>

              <div class="form-field">
                <label for="po-quantity" class="form-label">
                  {{ t('purchaseOrder.quantity') }} <span class="required">*</span>
                </label>
                <input
                  id="po-quantity"
                  v-model.number="form.quantity"
                  type="number"
                  min="1"
                  step="1"
                  class="form-input"
                  required
                />
              </div>

              <div class="form-field">
                <label for="po-unit-cost" class="form-label">
                  {{ t('purchaseOrder.unitCost') }} <span class="required">*</span>
                </label>
                <input
                  id="po-unit-cost"
                  v-model.number="form.unitCost"
                  type="number"
                  min="0.01"
                  step="0.01"
                  class="form-input"
                  required
                />
              </div>

              <div class="form-field">
                <label for="po-delivery" class="form-label">
                  {{ t('purchaseOrder.expectedDelivery') }} <span class="required">*</span>
                </label>
                <input
                  id="po-delivery"
                  v-model="form.expectedDeliveryDate"
                  type="date"
                  :min="todayString"
                  class="form-input"
                  required
                />
              </div>

              <div class="form-field total-field">
                <div class="form-label">{{ t('purchaseOrder.total') }}</div>
                <div class="total-value">{{ formattedFormTotal }}</div>
              </div>

              <div class="form-field full">
                <label for="po-notes" class="form-label">{{ t('purchaseOrder.notes') }}</label>
                <textarea
                  id="po-notes"
                  v-model="form.notes"
                  rows="3"
                  class="form-input form-textarea"
                  :placeholder="t('purchaseOrder.notesPlaceholder')"
                ></textarea>
              </div>

              <div v-if="submitError" class="error-message full">{{ submitError }}</div>
            </form>

            <!-- View mode -->
            <template v-else>
              <div v-if="viewLoading" class="state-message">{{ t('purchaseOrder.loading') }}</div>
              <div v-else-if="viewError" class="error-message">{{ viewError }}</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.poId') }}</div>
                  <div class="info-value sku">{{ purchaseOrder.id }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.status') }}</div>
                  <div class="info-value">
                    <span class="status-badge" :class="statusClass">{{ translatedStatus }}</span>
                  </div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.supplierName') }}</div>
                  <div class="info-value">{{ purchaseOrder.supplier_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.quantity') }}</div>
                  <div class="info-value">{{ purchaseOrder.quantity }} {{ t('purchaseOrder.units') }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.unitCost') }}</div>
                  <div class="info-value">{{ formatMoney(purchaseOrder.unit_cost) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.total') }}</div>
                  <div class="info-value strong">{{ formatMoney(viewTotal) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.expectedDelivery') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.expected_delivery_date) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.createdDate') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.created_date) }}</div>
                </div>
                <div class="info-item full">
                  <div class="info-label">{{ t('purchaseOrder.notes') }}</div>
                  <div class="info-value notes">{{ purchaseOrder.notes || t('purchaseOrder.noNotes') }}</div>
                </div>
              </div>
            </template>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="close">
              {{ mode === 'create' ? t('common.cancel') : t('common.close') }}
            </button>
            <button
              v-if="mode === 'create'"
              type="submit"
              form="po-form"
              class="btn-primary"
              :disabled="!isFormValid || submitting"
            >
              {{ submitting ? t('purchaseOrder.submitting') : t('purchaseOrder.submit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
import { ref, reactive, computed, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

// Number of days ahead used as the default expected delivery date
const DEFAULT_LEAD_TIME_DAYS = 14

// Format a Date as YYYY-MM-DD using LOCAL date parts. toISOString() would
// convert to UTC first and can shift the date by a day near midnight.
const toDateInputValue = (date) => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// Parse API dates safely. Date-only strings ("YYYY-MM-DD") are parsed by
// `new Date()` as UTC midnight, which displays as the previous day in
// timezones west of UTC, so build those from local parts instead.
const parseDate = (value) => {
  if (!value) return null
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value)
  return isNaN(date.getTime()) ? null : date
}

export default {
  name: 'PurchaseOrderModal',
  props: {
    isOpen: {
      type: Boolean,
      default: false
    },
    backlogItem: {
      type: Object,
      default: null
    },
    mode: {
      type: String,
      default: 'create',
      validator: (value) => ['create', 'view'].includes(value)
    }
  },
  emits: ['close', 'po-created'],
  setup(props, { emit }) {
    const { t, currentLocale, currentCurrency, translateProductName } = useI18n()

    const form = reactive({
      supplierName: '',
      quantity: 1,
      unitCost: null,
      expectedDeliveryDate: '',
      notes: ''
    })
    const submitting = ref(false)
    const submitError = ref(null)

    const purchaseOrder = ref(null)
    const viewLoading = ref(false)
    const viewError = ref(null)
    // Incremented on every fetch so a slow response for a previously
    // opened item cannot overwrite the data for the currently open one.
    let viewRequestId = 0

    const todayString = computed(() => toDateInputValue(new Date()))

    const shortage = computed(() => {
      if (!props.backlogItem) return 0
      const needed = Number(props.backlogItem.quantity_needed) || 0
      const available = Number(props.backlogItem.quantity_available) || 0
      return Math.max(needed - available, 0)
    })

    const isFormValid = computed(() => {
      const qty = form.quantity
      const cost = form.unitCost
      return (
        form.supplierName.trim().length > 0 &&
        Number.isInteger(qty) && qty > 0 &&
        typeof cost === 'number' && Number.isFinite(cost) && cost > 0 &&
        parseDate(form.expectedDeliveryDate) !== null
      )
    })

    const formTotal = computed(() => {
      const qty = Number(form.quantity)
      const cost = Number(form.unitCost)
      if (!Number.isFinite(qty) || !Number.isFinite(cost)) return 0
      return qty * cost
    })

    const formatMoney = (amount) => {
      const value = Number(amount)
      if (!Number.isFinite(value)) return '-'
      return formatCurrencyWithDecimals(value, currentCurrency.value, 2)
    }

    const formattedFormTotal = computed(() => formatMoney(formTotal.value))

    const viewTotal = computed(() => {
      if (!purchaseOrder.value) return 0
      return Number(purchaseOrder.value.quantity) * Number(purchaseOrder.value.unit_cost)
    })

    const translatedStatus = computed(() => {
      const status = purchaseOrder.value?.status
      if (!status) return '-'
      const key = `purchaseOrder.statuses.${String(status).toLowerCase()}`
      const translated = t(key)
      // t() returns the key itself when no translation exists; fall back to raw status
      return translated === key ? status : translated
    })

    const statusClass = computed(() => String(purchaseOrder.value?.status || '').toLowerCase())

    const formatDate = (value) => {
      const date = parseDate(value)
      if (!date) return '-'
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' })
    }

    // FastAPI returns `detail` as a string for HTTPException, or as an array
    // of { msg, loc, ... } objects for 422 validation errors. Normalize both
    // into a single readable message, falling back to a generic one.
    const extractErrorMessage = (err, fallback) => {
      const detail = err?.response?.data?.detail
      if (typeof detail === 'string' && detail.trim()) return detail
      if (Array.isArray(detail) && detail.length > 0) {
        const messages = detail.map(d => (d && d.msg) ? d.msg : String(d)).filter(Boolean)
        if (messages.length > 0) return messages.join('; ')
      }
      if (err?.response?.status === 409) return t('purchaseOrder.alreadyExists')
      if (err?.response?.status === 404) return t('purchaseOrder.notFound')
      return fallback
    }

    // Reset the form whenever the modal opens so values from a previously
    // opened backlog item (or a failed submit) never leak into a new one.
    const resetForm = () => {
      // Default the quantity to the shortage amount, since that is exactly
      // what must be ordered to fulfil the backlog; never below 1.
      form.supplierName = ''
      form.quantity = Math.max(shortage.value, 1)
      form.unitCost = null
      // Default delivery date: today + standard lead time
      const delivery = new Date()
      delivery.setDate(delivery.getDate() + DEFAULT_LEAD_TIME_DAYS)
      form.expectedDeliveryDate = toDateInputValue(delivery)
      form.notes = ''
      submitting.value = false
      submitError.value = null
    }

    const loadPurchaseOrder = async () => {
      const item = props.backlogItem
      if (!item) return
      const requestId = ++viewRequestId
      viewLoading.value = true
      viewError.value = null
      purchaseOrder.value = null
      try {
        const data = await api.getPurchaseOrderByBacklogItem(item.id)
        if (requestId !== viewRequestId) return
        purchaseOrder.value = data
      } catch (err) {
        if (requestId !== viewRequestId) return
        console.error('Failed to load purchase order:', err)
        viewError.value = extractErrorMessage(err, t('purchaseOrder.loadError'))
      } finally {
        if (requestId === viewRequestId) viewLoading.value = false
      }
    }

    watch(
      () => [props.isOpen, props.backlogItem?.id, props.mode],
      ([open]) => {
        if (!open || !props.backlogItem) return
        if (props.mode === 'view') {
          loadPurchaseOrder()
        } else {
          // Invalidate any in-flight view request and reset the form
          viewRequestId++
          resetForm()
        }
      }
    )

    const submit = async () => {
      if (!isFormValid.value || submitting.value || !props.backlogItem) return
      submitting.value = true
      submitError.value = null
      try {
        const payload = {
          backlog_item_id: String(props.backlogItem.id),
          supplier_name: form.supplierName.trim(),
          quantity: form.quantity,
          unit_cost: form.unitCost,
          expected_delivery_date: form.expectedDeliveryDate
        }
        const notes = form.notes.trim()
        if (notes) payload.notes = notes
        const created = await api.createPurchaseOrder(payload)
        emit('po-created', created)
      } catch (err) {
        console.error('Failed to create purchase order:', err)
        submitError.value = extractErrorMessage(err, t('purchaseOrder.createError'))
      } finally {
        submitting.value = false
      }
    }

    const close = () => {
      emit('close')
    }

    return {
      t,
      translateProductName,
      form,
      submitting,
      submitError,
      purchaseOrder,
      viewLoading,
      viewError,
      todayString,
      shortage,
      isFormValid,
      formattedFormTotal,
      viewTotal,
      translatedStatus,
      statusClass,
      formatMoney,
      formatDate,
      submit,
      close
    }
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 640px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem 2rem;
}

.context-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.5rem;
}

.context-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.75rem;
}

.context-grid {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  gap: 1rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem 1.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  min-width: 0;
}

.info-item.full,
.form-field.full,
.error-message.full {
  grid-column: 1 / -1;
}

.info-label,
.form-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
  word-break: break-word;
}

.info-value.sku {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.info-value.danger {
  color: #dc2626;
  font-weight: 600;
}

.info-value.strong {
  font-weight: 700;
}

.info-value.notes {
  white-space: pre-wrap;
  color: #334155;
}

.po-form {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem 1.5rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.required {
  color: #ef4444;
}

.form-input {
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.938rem;
  font-family: inherit;
  color: #0f172a;
  background: white;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.form-textarea {
  resize: vertical;
  min-height: 72px;
}

.total-field {
  justify-content: flex-end;
}

.total-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  padding: 0.25rem 0;
}

.state-message {
  padding: 2rem 0;
  text-align: center;
  color: #64748b;
}

.error-message {
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 0.875rem;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 6px;
  font-size: 0.813rem;
  font-weight: 600;
  background: #f1f5f9;
  color: #334155;
}

.status-badge.pending {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.ordered,
.status-badge.shipped {
  background: #dbeafe;
  color: #1e40af;
}

.status-badge.received {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.cancelled {
  background: #fecaca;
  color: #991b1b;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  background: #0f172a;
  border: 1px solid #0f172a;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1e293b;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 600px) {
  .po-form,
  .info-grid,
  .context-grid {
    grid-template-columns: 1fr;
  }
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
