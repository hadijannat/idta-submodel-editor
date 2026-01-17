/**
 * LocalForage instance for storing mapper recipes client-side
 */

import localforage from 'localforage';

export const recipeStore = localforage.createInstance({
  name: 'idta-submodel-editor',
  storeName: 'smart-mapper-recipes',
});
