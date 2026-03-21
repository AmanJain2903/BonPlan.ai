import * as auth from '../apis/auth';
import * as utils from '../apis/utils';
import * as planDraft from '../apis/planDraft';
import * as places from '../apis/places';

export const api = {
  auth: auth.api,
  utils: utils.api,
  planDraft: planDraft.api,
  places: places.api,
};
