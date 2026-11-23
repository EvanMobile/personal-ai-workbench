import { useI18n } from '../i18n'
import { cx } from '../utils'

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n()

  return (
    <div className="lang-switch" role="group" aria-label={t('language.label')}>
      <button
        type="button"
        className={cx('lang-switch-option', locale === 'zh-CN' && 'lang-switch-option-active')}
        aria-pressed={locale === 'zh-CN'}
        onClick={() => setLocale('zh-CN')}
      >
        {t('language.zh')}
      </button>
      <span className="lang-switch-divider" aria-hidden="true">
        /
      </span>
      <button
        type="button"
        className={cx('lang-switch-option', locale === 'en-US' && 'lang-switch-option-active')}
        aria-pressed={locale === 'en-US'}
        onClick={() => setLocale('en-US')}
      >
        {t('language.en')}
      </button>
    </div>
  )
}
