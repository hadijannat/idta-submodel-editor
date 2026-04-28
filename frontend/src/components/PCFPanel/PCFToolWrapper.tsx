import type { ToolComponentProps } from '../../tools/types';
import PCFPanel from './index';
import { isPCFTemplate } from './pcfUtils';

export default function PCFToolWrapper({ schema, form }: ToolComponentProps) {
  if (!schema || !isPCFTemplate(schema)) {
    return (
      <div className="wizard-panel">
        <div className="app-welcome">
          <h2>PCF Tools</h2>
          <p>
            Select an IDTA Carbon Footprint template to use the PCF calculator
            and validator.
          </p>
        </div>
      </div>
    );
  }

  return <PCFPanel schema={schema} form={form} />;
}
