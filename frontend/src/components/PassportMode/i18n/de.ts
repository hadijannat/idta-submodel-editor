/**
 * German translations for PassportMode.
 *
 * Translations follow Industry 4.0 / AAS terminology standards
 * as used in IDTA specifications.
 */

import type { PassportTranslations } from './types';

export const de: PassportTranslations = {
  toggle: {
    editor: 'Editor',
    passportView: 'Passport-Ansicht',
    viewModeLabel: 'Ansichtsmodus',
  },

  loading: {
    ariaLabel: 'Passport-Karte wird geladen',
    loading: 'Wird geladen...',
  },

  error: {
    title: 'Passport kann nicht angezeigt werden',
    description: 'Beim Rendern der Passport-Karte ist ein Fehler aufgetreten.',
    retry: 'Erneut versuchen',
    editorHint: 'oder wechseln Sie zum Editor-Modus, um die Daten zu überprüfen',
  },

  nameplate: {
    title: 'Digitales Typenschild',
    emptyMessage: 'Noch keine Typenschilddaten eingegeben.',
    emptyHint: 'Wechseln Sie zum Editor-Modus, um Hersteller- und Produktinformationen einzugeben.',
    identifierMarker: 'Identifikationsmarkierung',
    fields: {
      serialNumber: 'Seriennummer',
      manufacturerProductType: 'Herstellerprodukttyp',
      yearOfConstruction: 'Baujahr',
      countryOfOrigin: 'Herkunftsland',
      orderCode: 'Bestellnummer',
      batchNumber: 'Chargennummer',
      productArticleNumber: 'Produktartikelnummer',
      hardwareVersion: 'Hardware-Version',
      firmwareVersion: 'Firmware-Version',
      softwareVersion: 'Software-Version',
    },
  },

  pcf: {
    title: 'Product Carbon Footprint',
    emptyMessage: 'Noch keine CO₂-Fußabdruckdaten eingegeben.',
    emptyHint: 'Wechseln Sie zum Editor-Modus, um PCF-Werte einzugeben.',
    totalCo2e: 'Gesamt-CO₂e',
    perUnit: 'pro {{unit}}',
    derivedNote: 'Gesamtwert aus Phasenaufschlüsselung abgeleitet.',
    chartAriaLabel: 'CO₂-Fußabdruck-Aufschlüsselung nach Lebenszyklusphasen',
    chartAriaLabelWithBreakdown: 'CO₂-Fußabdruck-Aufschlüsselung: {{breakdown}}',
    breakdownMissing: 'Aufschlüsselung in diesem Datensatz nicht verfügbar.',
    calculationMethod: 'Berechnungsmethode',
    referenceUnit: 'Referenzeinheit',
    lifecyclePhase: 'Lebenszyklusphase',
    unknownPhase: 'Unbekannt',
    phases: {
      A1: 'Rohstoffbereitstellung',
      A2: 'Transport',
      A3: 'Herstellung',
      'A1-A3': 'Wiege bis Werkstor',
      A4: 'Vertrieb',
      A5: 'Einbau',
      B1: 'Nutzung',
      B2: 'Wartung',
      B3: 'Reparatur',
      B4: 'Ersatz',
      B5: 'Modernisierung',
      B6: 'Betriebsenergie',
      B7: 'Betriebswasser',
      C1: 'Rückbau',
      C2: 'Transport (Entsorgung)',
      C3: 'Abfallbehandlung',
      C4: 'Entsorgung',
      D: 'Vorteile & Lasten',
    },
  },

  generic: {
    emptyMessage: 'Noch keine Daten eingegeben.',
    emptyHint: 'Wechseln Sie zum Editor-Modus, um die Formularfelder auszufüllen.',
    templateLabel: 'Vorlage:',
    itemsCount: '{{count}} Einträge',
    itemLabel: 'Eintrag {{index}}',
  },

  export: {
    button: 'Exportieren',
    tooltip: 'Karte als PNG-Bild exportieren',
    exporting: 'Wird exportiert...',
    success: 'Karte erfolgreich exportiert',
    error: 'Export fehlgeschlagen: {{message}}',
    unsupported: 'Export wird in diesem Browser nicht unterstützt',
  },

  common: {
    co2e: 'CO₂e',
  },
};
