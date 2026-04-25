import * as auth from '../apis/auth';
import * as utils from '../apis/utils';
import * as plan from '../apis/plan';
import * as places from '../apis/places';
import * as admin from '../apis/admin';

export const api = {
  auth: auth.api,
  utils: utils.api,
  plan: plan.api,
  places: places.api,
  admin: admin.api,
};
