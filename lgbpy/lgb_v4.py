import csv
import datetime
import pandas as pd
import joblib
import lightgbm
from lightgbm import LGBMClassifier,cv
from scipy.stats import stats
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from skopt import BayesSearchCV
from skopt.callbacks import  DeltaXStopper
from data_process_v2 import processing

def predict(clf2, test_set):
    uid = pd.DataFrame()
    # test_set = processing(trainSpan=(1, 30), label=False)
    uid["user_id"] = test_set["user_id"]
    test_set = test_set.drop(labels=["user_id"], axis=1)
    # if isinstance(selector,RFECV):
    #     test_set_new = selector.transform(test_set.values)
    # elif isinstance(selector,list):
    #     test_set_new = test_set[selector]
    # else:
    #     test_set_new = test_set
    print("begin to make predictions")
    res = clf2.predict(test_set.values)
    uid["y_hat"] = pd.Series(res)
    uid["label"] = uid.groupby(by=["user_id"])["y_hat"].transform(lambda x: stats.mode(x)[0][0])
    str_time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))
    uid_file = "result/uid_" + str_time + ".csv"
    uid.to_csv(uid_file,header=True,index=False)
    active_users = (uid.loc[uid["label"] == 1]).user_id.unique().tolist()
    print(len(active_users))
    print(active_users)
    str_time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))
    submission_file = "result/submission_" + str_time + ".csv"
    with open(submission_file, "a", newline="") as f:
        writer = csv.writer(f)
        for i in active_users:
            writer.writerow([i])
# using this module ,one needs to deconstruct some of the features in data_process
keep_feature = ["user_id",
                "register_day_rate", "register_type_rate",
                "register_type_device", "device_type_rate", "device_type_register",
                "user_app_launch_register_mean_time",
                "user_app_launch_rate", "user_app_launch_gap",
                "user_video_create_register_mean_time",
                "user_video_create_rate", "user_video_create_day", "user_video_create_gap",
                 "user_activity_register_mean_time", "user_activity_rate",
                 "user_activity_frequency",
                 "user_activity_day_rate", "user_activity_gap",
                 "user_page_num", "user_video_id_num",
                 "user_author_id_num", "user_author_id_video_num",
                 "user_action_type_num"
                  ]
def run():
    print("begin to load the trainset1")
    train_set1 = processing(trainSpan=(1,10),label=True)
    # print(train_set1.describe())
    print("begin to load the trainset2")
    train_set2 = processing(trainSpan=(11,20),label=True)
    # print(train_set2.describe())
    print("begin to merge the trainsets")
    train_set = pd.concat([train_set1,train_set2],axis=0)
    print(train_set.describe())
    print("begin to drop the duplicates")
    train_set.drop_duplicates(subset=keep_feature,inplace=True)
    print(train_set.describe())
    train_label =train_set["label"]
    train_set = train_set.drop(labels=["label","user_id"], axis=1)

    # train_x, val_x,train_y,val_y = train_test_split(train_set.values,train_label.values,test_size=0.33,random_state=42,shuffle=True)
    print("begin to make prediction with plain features and without tuning parameters")
    initial_params = {
        "n_estimators":600,
        "n_jobs":-1,
        "silent":True,
        "metric":"binary_logloss",
        'max_depth': 6,
        "max_bin": 100,
        "num_leaves": 64,
        'min_child_weight': 0,
        'min_child_samples': 100,
        "min_split_gain": 0.0,
        "learning_rate": 0.02,
        "colsample_bytree": 0.9,
        "subsample": 0.8,
        'reg_alpha': 0.0,
        'reg_lambda': 0.0,
    }
    train_data = lightgbm.Dataset(train_set.values, label=train_label.values, feature_name=list(train_set.columns))

    scoring = {'AUC': 'roc_auc', 'f1': "f1"}
    clf1 = GridSearchCV(LGBMClassifier(**initial_params),
                      param_grid={"n_estimators":[600,800],"num_leaves": [32,64],"learning_rate": [0.01,0.02],},
                      scoring=scoring, cv=5, refit='f1',n_jobs=-1,verbose=0)
    # clf1.fit(train_set.values, train_label.values)
    # cv_results = cv(initial_params,train_data,num_boost_round=800,nfold=4,early_stopping_rounds=30,verbose_eval=True)
    # bst = lgb.cv(initial_params, train_data, num_boost_round=1000, nfold=3, early_stopping_rounds=30)
    print(clf1.best_score_)
    print(clf1.best_params_)
    # clf1 = LGBMClassifier(**initial_params)
    # clf1.fit(X=train_x,y=train_y,eval_set=(val_x,val_y),early_stopping_rounds=20,eval_metric="auc")
    print("load the test dataset")
    test_set = processing(trainSpan=(21, 30), label=False)
    print("begin to make prediction")
    predict(clf1,test_set)

    str_time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))
    print("begin to get important features")
    feature_names = train_set.columns
    feature_importances = clf1.best_estimator_.feature_importances_
    print(feature_importances)
    print(feature_names)

    with open("kuaishou_stats.csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["feature importance of catboost for tencent-crt", str_time])
        # writer.writerow(eval_metrics)
        feature_score_name = sorted(zip(feature_importances, feature_names), reverse=True)
        for score, name in feature_score_name:
            print('{}: {}'.format(name, score))
            writer.writerow([name, score])
    sorted_feature_name = [name for score, name in feature_score_name]
    print(sorted_feature_name)

    print("begin to tune the parameters with the selected feature")
    paramsSpace = {
        "n_estimators": (600, 2000),
        "max_depth": (3, 8),
        "max_bin": (80, 200),
        "num_leaves": (16, 200),
        "min_child_weight": (1e-3, 1e3, 'log-uniform'),
        "min_child_samples": (16, 256),
        "min_split_gain": (1e-6, 1.0, 'log-uniform'),
        "learning_rate": (1e-6, 1.0, 'log-uniform'),
        "colsample_bytree": (0.6, 1.0, 'uniform'),
        "subsample": (0.6, 1.0, 'uniform'),
        'reg_alpha': (1e-3, 1e3, 'log-uniform'),
        'reg_lambda': (1e-3, 1e3, 'log-uniform'),
        "scale_pos_weight": (0.0, 1.0, 'uniform'),
    }

    def tune_parameter(X, y, clf, params):
        # X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
        gs = BayesSearchCV(
            estimator=clf, search_spaces=params,
            scoring="f1", n_iter=60,optimizer_kwargs={"base_estimator":"GBRT"},
            verbose=0, n_jobs=-1, cv=5, refit=True, random_state=1234
        )
        gs.fit(X, y,callback=DeltaXStopper(0.0000001))
        best_params = gs.best_params_
        best_score = gs.best_score_
        print(best_params)
        print(best_score)
        str_time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))
        with open("kuaishou_stats.csv", 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["the best params for lightgbm: "])
            for key, value in best_params.items():
                writer.writerow([key, value])
            writer.writerow(["the best score for lightgbm: ", best_score,str_time])
        return gs

    model = LGBMClassifier(**initial_params)
    clf2 = tune_parameter(train_set.values,train_label.values,model,paramsSpace)
    print("parameter tuning over, begin to save the model!")
    str_time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))

    model_name = "lightgbm_" + str_time + ".pkl"
    joblib.dump(clf2, model_name)

    print("begin to process the whole dataset and ready to feed into the fitted model")
    predict(clf2,test_set)
    str_time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"))
    print("begin to get important features")
    feature_names = train_set.columns
    feature_importances = clf2.best_estimator_.feature_importances_
    print(feature_importances)
    print(feature_names)

    with open("kuaishou_stats.csv", 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["feature importance of catboost for tencent-crt", str_time])
        # writer.writerow(eval_metrics)
        feature_score_name = sorted(zip(feature_importances, feature_names), reverse=True)
        for score, name in feature_score_name:
            print('{}: {}'.format(name, score))
            writer.writerow([name, score])
    sorted_feature_name = [name for score, name in feature_score_name]
    print(sorted_feature_name)
if __name__=="__main__":
    run()