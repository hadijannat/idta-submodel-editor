import type { ToolComponentProps } from '../../tools/types';

export function DppBuilderPanel({ templateName }: ToolComponentProps) {
  return (
    <section className="wizard-card" aria-label="DPP builder">
      <h3>Digital Product Passport Builder</h3>
      <p>
        Build Digital Product Passport content for <strong>{templateName}</strong>.
      </p>
      <p>
        This step currently validates basic readiness and reserves a stable place in
        the wizard flow for upcoming DPP authoring capabilities.
      </p>
    </section>
  );
}

export default DppBuilderPanel;
