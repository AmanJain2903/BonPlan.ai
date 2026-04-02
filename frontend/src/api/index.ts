import * as auth from '../apis/auth';
import * as utils from '../apis/utils';
import * as plan from '../apis/plan';
import * as places from '../apis/places';

export const api = {
  auth: auth.api,
  utils: utils.api,
  plan: plan.api,
  places: places.api,
};
